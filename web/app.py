import json
from html import escape as html_escape
import logging
import os
import os.path as osp
from pathlib import Path
import re
import random
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from io import BytesIO

import markdown
import yaml
from flask import Flask, abort, jsonify, render_template, request, send_from_directory, send_file, session, redirect, url_for
from pydantic import ValidationError
from weasyprint import HTML, CSS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from recipe_core.recipe_lib import RecipeData, CategoryType, MealType, FoodType, parse_quantity, recipe_title
from recipe_core.foods import list_foods, create_food, update_food, delete_food
from recipe_core.shopping_list import (
    find_recipe_dirs,
    generate_shopping_list_md,
    get_merged_shopping_list,
    get_shopping_list_data
)
from recipe_core.mailer import build_message, send_email
from recipe_core.gemini_importer import extract_recipe, ImportResult, MAX_RETRIES
from recipe_core.recipe_chat import ChatReply, build_catalog, chat as recipe_chat, make_client
from recipe_core.recipe_search import search_recipes
from recipe_core.recipe_revise import revise_recipe
from recipe_core.gemini import friendly_error
from recipe_core.push import PushStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_this_dir = os.path.dirname(__file__)
with open(os.path.join(_this_dir, "config.yaml")) as f:
    config = yaml.safe_load(f)

DATA_DIR     = os.environ.get("RECIPES_DATA_DIR") or os.path.join(_this_dir, config["app"]["data_dir"])
RECIPES_DIR  = os.path.join(DATA_DIR, config["app"]["recipes_dir"])
PENDING_DIR  = os.path.join(DATA_DIR, config["app"]["pending_dir"])
ARCHIVED_DIR = os.path.join(DATA_DIR, config["app"]["archived_dir"])
STATE_FILE  = os.path.join(_this_dir, config["app"]["state_file"])
OUTPUT_DIR  = os.path.join(_this_dir, config["app"]["output_dir"])
PUSH = PushStore(os.path.join(_this_dir, "instance"))

# Email configuration
EMAIL_CONFIG = config.get("email", {})
SMTP_SERVER = EMAIL_CONFIG.get("smtp_server", "smtp.gmail.com")
SMTP_PORT = EMAIL_CONFIG.get("smtp_port", 587)

# Feature flags based on environment variables
GMAIL_SENDER = os.environ.get("GMAIL_SENDER")
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

EMAIL_ENABLED = bool(GMAIL_SENDER and GMAIL_PASSWORD)
IMPORT_ENABLED = bool(GEMINI_API_KEY)

if not EMAIL_ENABLED:
    logger.warning("Email features disabled: GMAIL_SENDER and/or GMAIL_APP_PASSWORD not set")
if not IMPORT_ENABLED:
    logger.warning("Recipe import disabled: GEMINI_API_KEY not set")

# ---------------------------------------------------------------------------
# Recipe dataclass
# ---------------------------------------------------------------------------

@dataclass
class Recipe:
    slug:             str
    name:             str
    md_filename:      str
    path:             str
    category:         str  = ""
    meal:             str  = ""
    selected:         bool = False
    weeks_since_last: int  = 1

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)

@app.context_processor
def _asset_helper():
    """asset('css/style.css') -> /static/css/style.css?v=<mtime>. The service worker
    caches static files by full URL, so a changed file gets a new cache entry."""
    def asset(filename: str) -> str:
        try:
            version = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
        except OSError:
            version = 0
        return url_for("static", filename=filename, v=version)
    return {"asset": asset}
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# ---------------------------------------------------------------------------
# State file (JSON) — persists stateful data like 'selected' and 'weeks_since_last'
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    """Load state from JSON file. Returns empty dict if file doesn't exist."""
    if osp.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def _save_state(state: dict):
    """Write state dict to JSON file atomically (temp file + rename), so concurrent
    writers or a crash mid-write can't leave a truncated or interleaved file."""
    os.makedirs(osp.dirname(STATE_FILE), exist_ok=True)
    tmp = f"{STATE_FILE}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)

# ---------------------------------------------------------------------------
# Recipe store — filesystem + state file
# ---------------------------------------------------------------------------

def _find_md_file(recipe_dir: str) -> str:
    """Return the first markdown file found in recipe_dir, or empty string."""
    for f in os.listdir(recipe_dir):
        if f.endswith(".md"):
            return f
    return ""

def _load_category_meal(recipe_dir: str, slug: str) -> tuple[str, str]:
    """Read `category`/`meal` out of a recipe directory's recipe.yaml, if present."""
    category = ""
    meal = ""
    yaml_path = osp.join(recipe_dir, "recipe.yaml")
    if osp.exists(yaml_path):
        try:
            recipe_data = RecipeData.from_yaml(yaml_path)
            category = recipe_data.category.value
            meal = recipe_data.meal.value
        except Exception as e:
            logger.warning(f"Failed to load recipe data for {slug}: {e}")
    return category, meal

def _recipe_name(recipe_dir: str, slug: str) -> str:
    """Display name: recipe.md's `# Title`, else recipe.yaml `name`, else the slug."""
    title = recipe_title(recipe_dir)
    if title:
        return title
    try:
        with open(osp.join(recipe_dir, "recipe.yaml")) as f:
            raw = yaml.safe_load(f) or {}
        if isinstance(raw, dict) and raw.get("name"):
            return str(raw["name"])
    except (OSError, yaml.YAMLError):
        pass
    return slug.replace("_", " ").title()

def get_all_recipes() -> list[Recipe]:
    """
    Build the current recipe list from the filesystem, enriched with
    stateful fields (selected, weeks_since_last) from the state file.
    Slugs present in the state file but no longer on disk are ignored.
    """
    state = _load_state()
    recipes = []

    for recipe_dir in find_recipe_dirs(RECIPES_DIR):
        path = Path(recipe_dir).relative_to(RECIPES_DIR)
        slug = osp.basename(recipe_dir)
        entry = state.get(slug, {})

        category, meal = _load_category_meal(recipe_dir, slug)

        recipes.append(Recipe(
            slug             = slug,
            path             = str(path),
            name             = _recipe_name(recipe_dir, slug),
            md_filename      = _find_md_file(recipe_dir),
            category         = category,
            meal             = meal,
            selected         = entry.get("selected", False),
            weeks_since_last = entry.get("weeks_since_last", 1),
        ))

    return recipes

def _update_state(slug: str, **kwargs):
    """Merge kwargs into the state entry for slug and save."""
    state = _load_state()
    entry = state.get(slug, {})
    entry.update(kwargs)
    state[slug] = entry
    _save_state(state)

# ---------------------------------------------------------------------------
# Schedule configuration
# ---------------------------------------------------------------------------

PLAN_DEFAULTS = {
    "enabled": False,
    "num_recipes": 3,
    "frequency_weeks": 1,     # 1 = every week, 2 = every other week
    "day_of_week": 6,         # 0 = Monday ... 6 = Sunday (APScheduler convention)
    "send_time": "09:00",
    "fresh_start": True,      # replace last week's picks instead of keeping them
    "notify": True,           # push notification to subscribed devices
    "send_email": False,
    "recipients": "",
}

def _get_schedule_config() -> dict:
    """Weekly plan settings from the state file, with defaults for missing keys.
    Older configs (email-only) predate send_email: keep emailing if they had recipients."""
    stored = _load_state().get("_schedule_config", {})
    config = {**PLAN_DEFAULTS, **stored}
    if "send_email" not in stored:
        config["send_email"] = bool(stored.get("recipients", "").strip())
    return config

def _save_schedule_config(config: dict):
    """Save schedule configuration to state file."""
    state = _load_state()
    state["_schedule_config"] = config
    _save_state(state)

def _is_recipe_available(slug: str, min_period_weeks: int) -> bool:
    """
    Check if a recipe is available for selection based on when it was last used.

    Args:
        slug: Recipe slug
        min_period_weeks: Minimum weeks to wait before selecting again

    Returns:
        True if recipe can be selected
    """
    state = _load_state()
    entry = state.get(slug, {})
    last_used = entry.get("last_used_date")

    if not last_used:
        return True

    last_used_date = datetime.fromisoformat(last_used).date()
    weeks_since = (date.today() - last_used_date).days / 7

    return weeks_since >= min_period_weeks

def select_recipes_for_schedule(num_recipes: int) -> list[str]:
    """
    Select recipes for scheduled email, using currently selected recipes first,
    then filling with random available recipes.

    Args:
        num_recipes: Total number of recipes to select

    Returns:
        List of recipe slugs
    """
    all_recipes = get_all_recipes()

    # Get currently selected recipes
    selected_slugs = [r.slug for r in all_recipes if r.selected]

    # If we already have enough, just use those
    if len(selected_slugs) >= num_recipes:
        return selected_slugs[:num_recipes]

    # Load recipe metadata to get min_period_weeks
    _, metas = _get_shopping_list_data()

    # Get available recipes (not currently selected and past min period)
    available = []
    for recipe in all_recipes:
        if recipe.slug not in selected_slugs:
            recipe_data = metas.get(recipe.slug)
            if recipe_data and recipe_data.enabled:
                min_period = recipe_data.min_period_weeks
                if _is_recipe_available(recipe.slug, min_period):
                    available.append(recipe.slug)

    # Randomly select from available recipes
    num_needed = num_recipes - len(selected_slugs)
    if available and num_needed > 0:
        random.shuffle(available)
        selected_slugs.extend(available[:num_needed])

    return selected_slugs

def update_recipe_usage(slugs: list[str]):
    """Mark recipes as used today."""
    today = date.today().isoformat()
    for slug in slugs:
        _update_state(slug, last_used_date=today)

def _email_shopping_list(slugs: list[str], recipients: list[str]):
    """Email a PDF shopping list for the given recipes."""
    _, metas = _get_shopping_list_data()
    names = [metas[slug].name for slug in slugs if slug in metas]
    pdf_bytes = _shopping_list_pdf(slugs=slugs)

    today = date.today().isoformat()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_path = osp.join(OUTPUT_DIR, f"shopping-list-{today}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    try:
        body = f"Your shopping list for {len(slugs)} recipes.\n\nRecipes:\n" + "\n".join(f"- {n}" for n in names)
        message = build_message(sender=GMAIL_SENDER, recipients=recipients,
                                subject=f"Weekly Shopping List - {today}", body=body, attachments=[pdf_path])
        send_email(sender=GMAIL_SENDER, password=GMAIL_PASSWORD, recipients=recipients,
                   message=message, server=SMTP_SERVER, port=SMTP_PORT)
    finally:
        if osp.exists(pdf_path):
            os.remove(pdf_path)
    logger.info("Shopping list emailed to: %s", ", ".join(recipients))

def run_weekly_plan(force: bool = False) -> dict:
    """
    Pick this week's recipes, put them on the shopping list, then notify subscribed
    devices and (optionally) email the list. Scheduled by _reschedule_email_job();
    force=True runs it now regardless of the enabled/frequency settings.
    """
    config = _get_schedule_config()
    state = _load_state()
    last = state.get("_week_plan", {}).get("created")

    if not force:
        if not config["enabled"]:
            return {"skipped": "disabled"}
        if config["frequency_weeks"] > 1 and last:
            days = (datetime.now() - datetime.fromisoformat(last)).days
            if days < 7 * config["frequency_weeks"] - 3:
                logger.info("Weekly plan: last run %d days ago, skipping this week", days)
                return {"skipped": "not due"}

    if config["fresh_start"]:
        for r in get_all_recipes():
            if r.selected:
                _update_state(r.slug, selected=False)

    slugs = select_recipes_for_schedule(int(config["num_recipes"]))
    if not slugs:
        logger.warning("Weekly plan: no recipes available")
        return {"skipped": "no recipes available"}

    for slug in slugs:
        _update_state(slug, selected=True)
    update_recipe_usage(slugs)
    _invalidate_shopping_list_cache()

    _, metas = _get_shopping_list_data()
    names = [metas[s].name if s in metas else s.replace("_", " ").title() for s in slugs]
    state = _load_state()
    state["_week_plan"] = {"created": datetime.now().isoformat(timespec="seconds"),
                           "slugs": slugs, "names": names}
    _save_state(state)
    result = {"slugs": slugs, "names": names, "notified": 0, "emailed": False}

    if config["notify"]:
        result["notified"] = PUSH.send_all(
            title="This week's recipes",
            body=", ".join(names) + ". Tap to review and shop.",
            url="/", tag="weekly-plan")

    recipients = [e.strip() for e in config["recipients"].replace(";", ",").split(",") if e.strip()]
    if config["send_email"] and recipients and EMAIL_ENABLED:
        try:
            _email_shopping_list(slugs, recipients)
            result["emailed"] = True
        except Exception as e:
            logger.error("Weekly plan email failed: %s", e, exc_info=True)

    logger.info("Weekly plan: %s (notified %d devices)", ", ".join(names), result["notified"])
    return result

def _scheduled_weekly_plan():
    try:
        run_weekly_plan()
    except Exception as e:
        logger.error("Weekly plan failed: %s", e, exc_info=True)

# ---------------------------------------------------------------------------
# Shopping list helpers
# ---------------------------------------------------------------------------

_shopping_list_cache: dict = {}

def _get_shopping_list_data():
    """Return cached shopping list data, loading from disk if needed."""
    if not _shopping_list_cache:
        lists, metas = get_shopping_list_data(RECIPES_DIR)
        _shopping_list_cache["lists"] = lists
        _shopping_list_cache["metas"] = metas
    return _shopping_list_cache["lists"], _shopping_list_cache["metas"]

def _invalidate_shopping_list_cache():
    _shopping_list_cache.clear()

def get_shopping_list_html(show_sources: bool = False) -> str:
    selected_slugs = [r.slug for r in get_all_recipes() if r.selected]

    if not selected_slugs:
        return "<em>Select recipes to generate shopping list.</em>"

    lists, metas = _get_shopping_list_data()
    
    main, secondary = get_merged_shopping_list(selected_slugs, lists)
    
    names = [metas[slug].name for slug in selected_slugs]
    md = generate_shopping_list_md(names, selected_slugs, main, secondary, show_sources=show_sources)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(osp.join(OUTPUT_DIR, "shopping_list.md"), "w") as f:
        f.write(md)

    return markdown.markdown(md, extensions=[
        "tables",
        "fenced_code",
        "nl2br",
        "sane_lists"
    ])

# ---------------------------------------------------------------------------
# Routes — home
# ---------------------------------------------------------------------------

@app.route("/service-worker.js")
def service_worker():
    """Serve the service worker from the root so its scope covers every page."""
    response = send_from_directory(app.static_folder, "service-worker.js",
                                   mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache"
    return response

@app.route("/api/features")
def features():
    """Return which features are enabled based on env vars."""
    return jsonify({
        "email_enabled": EMAIL_ENABLED,
        "import_enabled": IMPORT_ENABLED
    })

@app.route("/deselect/<slug>", methods=["POST"])
def deselect(slug):
    _update_state(slug, selected=False)
    _invalidate_shopping_list_cache()
    return jsonify({"success": True, "selected": False})

@app.route("/markdown/shopping_list")
def update_shopping_list_html():
    show_sources = request.args.get("show_sources", "false").lower() == "true"
    return jsonify({"html": get_shopping_list_html(show_sources=show_sources)})

@app.route("/send_list", methods=["POST"])
def send_list():
    """Send shopping list PDF via email"""
    if not EMAIL_ENABLED:
        return jsonify({
            "success": False,
            "error": "Email feature disabled. Set GMAIL_SENDER and GMAIL_APP_PASSWORD environment variables to enable."
        }), 503

    data = request.get_json()
    email_input = data.get("email", "").strip()

    if not email_input:
        return jsonify({"success": False, "error": "No email addresses provided"}), 400

    # Parse email addresses (split by semicolon or comma)
    recipients = [e.strip() for e in email_input.replace(";", ",").split(",") if e.strip()]

    if not recipients:
        return jsonify({"success": False, "error": "No valid email addresses"}), 400

    # Generate PDF
    selected_slugs = [r.slug for r in get_all_recipes() if r.selected]

    if not selected_slugs:
        return jsonify({"success": False, "error": "No recipes selected"}), 400

    sender = GMAIL_SENDER
    password = GMAIL_PASSWORD

    try:
        lists, metas = _get_shopping_list_data()
        main, secondary = get_merged_shopping_list(selected_slugs, lists)
        names = [metas[slug].name for slug in selected_slugs]
        md = generate_shopping_list_md(names, selected_slugs, main, secondary, show_sources=False)

        # Convert markdown to HTML
        html_content = markdown.markdown(md, extensions=[
            "tables",
            "fenced_code",
            "nl2br",
            "sane_lists"
        ])

        # Wrap in proper HTML document with styling
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: letter;
                    margin: 0.75in;
                }}
                body {{
                    font-family: Arial, sans-serif;
                    font-size: 11pt;
                    line-height: 1.5;
                    color: #000;
                }}
                h1 {{
                    font-size: 20pt;
                    font-weight: bold;
                    color: #000;
                    margin-top: 0;
                    margin-bottom: 0.5em;
                    padding-bottom: 0.3em;
                    border-bottom: 2px solid #333;
                }}
                h2 {{
                    font-size: 16pt;
                    font-weight: bold;
                    color: #000;
                    margin-top: 1em;
                    margin-bottom: 0.4em;
                    padding-bottom: 0.2em;
                    border-bottom: 1px solid #666;
                    page-break-after: avoid;
                }}
                h3 {{
                    font-size: 13pt;
                    font-weight: bold;
                    color: #000;
                    margin-top: 0.8em;
                    margin-bottom: 0.3em;
                    padding-left: 0.3em;
                    border-left: 3px solid #333;
                    page-break-after: avoid;
                }}
                ul, ol {{
                    margin-bottom: 0.5em;
                    padding-left: 1.5em;
                }}
                li {{
                    margin-bottom: 0.2em;
                    page-break-inside: avoid;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 1em;
                    page-break-inside: avoid;
                }}
                th, td {{
                    padding: 6px 10px;
                    border: 1px solid #999;
                    text-align: left;
                }}
                th {{
                    background-color: #f0f0f0;
                    font-weight: bold;
                }}
                tr {{
                    page-break-inside: avoid;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # Generate PDF in memory
        pdf_bytes = HTML(string=full_html).write_pdf()

        # Save PDF temporarily
        today = date.today().isoformat()
        filename = f"shopping-list-{today}.pdf"
        temp_pdf_path = osp.join(OUTPUT_DIR, filename)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_bytes)

        # Build and send email
        subject = f"Shopping List - {today}"
        body = f"Please find attached your shopping list for {len(selected_slugs)} selected recipes."

        message = build_message(
            sender=sender,
            recipients=recipients,
            subject=subject,
            body=body,
            attachments=[temp_pdf_path]
        )

        send_email(
            sender=sender,
            password=password,
            recipients=recipients,
            message=message,
            server=SMTP_SERVER,
            port=SMTP_PORT
        )

        # Clean up temp file
        if osp.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

        logger.info("Shopping list sent to: %s", ", ".join(recipients))
        return jsonify({"success": True, "message": f"Email sent to {len(recipients)} recipient(s)"})

    except Exception as e:
        logger.error("Failed to send email: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

def _shopping_list_pdf(dismissed: set[str] | None = None, custom: list[dict] | None = None,
                       slugs: list[str] | None = None) -> bytes:
    """Printable shopping list PDF: numbered recipes, then Item / Quantity / Recipe tables
    (recipe column uses those numbers). `dismissed` holds the list page's removed item keys
    ("Category::name"); `custom` its added items ({name, quantity}). `slugs` defaults to the
    current selection."""
    dismissed = dismissed or set()
    all_recipes = get_all_recipes()
    names_by_slug = {r.slug: r.name for r in all_recipes}
    if slugs is None:
        slugs = [r.slug for r in sorted(all_recipes, key=lambda r: r.name) if r.selected]
    number = {slug: i + 1 for i, slug in enumerate(slugs)}

    lists, _ = _get_shopping_list_data()
    main, secondary = get_merged_shopping_list(slugs, lists) if slugs else ({}, {})

    def groups(merged: dict) -> list:
        out = []
        for category, ingredients in merged.items():
            items = [{
                "name": mi.food.get_name(),
                "quantity": mi.format_quantity(slugs),
                "recipes": ", ".join(str(n) for n in sorted(number[s] for s in mi.all_source_slugs() if s in number)),
            } for mi in ingredients if f"{category}::{mi.food.get_name()}" not in dismissed]
            if items:
                out.append((category, items))
        return out

    mine = [{"name": str(c.get("name", "")).strip(), "quantity": str(c.get("quantity") or ""), "recipes": ""}
            for c in (custom or []) if isinstance(c, dict) and str(c.get("name", "")).strip()]
    to_buy = ([("My items", mine)] if mine else []) + groups(main)
    html = render_template(
        "shopping_list_pdf.html",
        today=date.today().strftime("%A, %B %-d, %Y"),
        recipes=[names_by_slug.get(s, s.replace("_", " ").title()) for s in slugs],
        sections=[{"title": "To buy", "groups": to_buy},
                  {"title": "Probably have", "groups": groups(secondary)}],
    )
    return HTML(string=html).write_pdf()

@app.route("/download_shopping_list_pdf", methods=["GET", "POST"])
def download_shopping_list_pdf():
    """Shopping list PDF, shown inline. The list page POSTs its client-side state as a
    form field `state` = JSON {dismissed: [...], custom: [{name, quantity}]}."""
    try:
        client_state = json.loads(request.form.get("state") or "{}")
    except ValueError:
        client_state = {}
    if not isinstance(client_state, dict):
        client_state = {}
    pdf = _shopping_list_pdf(dismissed=set(client_state.get("dismissed") or []),
                             custom=client_state.get("custom") or [])
    return send_file(BytesIO(pdf), mimetype="application/pdf", as_attachment=False,
                     download_name=f"shopping-list-{date.today().isoformat()}.pdf")

# ---------------------------------------------------------------------------
# Routes — recipe list
# ---------------------------------------------------------------------------

@app.route("/recipes_list")
def recipes_list():
    recipes = sorted(get_all_recipes(), key=lambda r: r.name)
    archived_recipes = sorted(_list_flat_recipes(ARCHIVED_DIR, "archived"), key=lambda r: r["name"])
    pending_recipes = sorted(_list_flat_recipes(PENDING_DIR, "pending"), key=lambda r: r["name"])
    return render_template(
        "recipes_list.html",
        recipes=[asdict(r) for r in recipes],
        archived_recipes=archived_recipes,
        pending_recipes=pending_recipes,
        active_page="recipes_list",
        email_enabled=EMAIL_ENABLED,
        import_enabled=IMPORT_ENABLED,
    )

def get_shopping_list_items() -> dict:
    """
    Return the merged shopping list for the currently selected recipes, split
    into 'main' (things to buy) and 'secondary' (likely already have) — each
    {category: [{name, quantity, vendor, sources}, ...]} — for the
    interactive table page. 'sources' is [{slug, name}, ...] of the recipes
    that contributed the ingredient, for the ingredient detail popup.
    """
    all_recipes = get_all_recipes()
    selected_slugs = [r.slug for r in all_recipes if r.selected]
    if not selected_slugs:
        return {"main": {}, "secondary": {}}

    recipe_names = {r.slug: r.name for r in all_recipes}
    lists, metas = _get_shopping_list_data()
    main, secondary = get_merged_shopping_list(selected_slugs, lists)

    def _to_items(group: dict) -> dict[str, list[dict]]:
        items: dict[str, list[dict]] = {}
        for category, ingredients in group.items():
            for mi in ingredients:
                sources = [
                    {"slug": slug, "name": recipe_names.get(slug, slug.replace("_", " ").title())}
                    for slug in mi.all_source_slugs()
                ]
                items.setdefault(category, []).append({
                    "name": mi.food.get_name(),
                    "quantity": mi.format_quantity(selected_slugs),
                    "vendor": mi.food.preferred_vendor or "",
                    "sources": sources,
                })
        return items

    return {"main": _to_items(main), "secondary": _to_items(secondary)}

@app.route("/")
def index():
    """Shopping list page: interactive table (sortable by name/category), built from selected recipes."""
    recipes = get_all_recipes()
    selected = sorted([r for r in recipes if r.selected], key=lambda r: r.name)
    return render_template(
        "index.html",
        active_page="home",
        email_enabled=EMAIL_ENABLED,
        import_enabled=IMPORT_ENABLED,
        recipes=selected,
        shopping_items=get_shopping_list_items(),
        week_id=_load_state().get("_week_plan", {}).get("created"),
    )

@app.route("/recipes_list/toggle/<slug>", methods=["POST"])
def toggle(slug):
    recipes = get_all_recipes()
    recipe = next((r for r in recipes if r.slug == slug), None)
    if recipe is None:
        abort(404)
    new_selected = not recipe.selected
    _update_state(slug, selected=new_selected)
    _invalidate_shopping_list_cache()
    return jsonify({"success": True, "selected": new_selected})

@app.route("/recipes/<path:file>")
def serve_recipe_file(file):
    recipes = get_all_recipes()
    slug, file = file.split("/", 1)
    recipe = next((r for r in recipes if r.slug == slug), None)
    if recipe is None:
        abort(404)
    return send_from_directory(osp.join(RECIPES_DIR, recipe.path), file)

@app.route("/pending/<slug>/<path:file>")
def serve_pending_file(slug, file):
    """Serve files from pending recipe directory."""
    pending_recipe_dir = osp.join(PENDING_DIR, slug)
    if not osp.exists(pending_recipe_dir):
        abort(404)
    return send_from_directory(pending_recipe_dir, file)

@app.route("/archived/<slug>/<path:file>")
def serve_archived_file(slug, file):
    """Serve files from archived recipe directory."""
    archived_recipe_dir = osp.join(ARCHIVED_DIR, slug)
    if not osp.exists(archived_recipe_dir):
        abort(404)
    return send_from_directory(archived_recipe_dir, file)

@app.route("/markdown/recipe/<recipe_name>")
def get_markdown_recipe(recipe_name):
    recipes = get_all_recipes()
    recipe = next((r for r in recipes if r.name == recipe_name), None)
    if recipe is None:
        abort(404)

    md_file = osp.join(RECIPES_DIR, recipe.path, recipe.md_filename)
    if not md_file.endswith(".md") or not osp.exists(md_file):
        abort(404)

    with open(md_file, "r", encoding="utf-8") as f:
        md_content = f.read()

    html_content = markdown.markdown(md_content, extensions=[
        "tables",
        "fenced_code",
        "nl2br",
        "sane_lists"
    ])
    html_content = re.sub(
        r'src="([^":]+)"',
        lambda m: f'src="recipes/{recipe.slug}/{m.group(1)}"',
        html_content,
    )
    return jsonify({"filename": md_file, "content": html_content})

# ---------------------------------------------------------------------------
# Recipe management helpers
# ---------------------------------------------------------------------------

def save_pending(result: ImportResult, pending_dir: str = PENDING_DIR):
    """Save an extracted recipe to the pending directory."""
    recipe_dir = osp.join(pending_dir, result.slug)
    os.makedirs(recipe_dir, exist_ok=True)

    # Save YAML
    yaml_path = osp.join(recipe_dir, "recipe.yaml")
    with open(yaml_path, "w") as f:
        # mode="json" turns enums into plain strings; mode="python" wrote !!python/object
        # tags that yaml.safe_load (used everywhere else) refuses to read.
        yaml.safe_dump(result.recipe_data.model_dump(mode="json", exclude_none=True), f,
                       default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Save Markdown
    md_path = osp.join(recipe_dir, "recipe.md")
    with open(md_path, "w") as f:
        f.write(result.markdown)

    # Save source info
    info_path = osp.join(recipe_dir, "source.txt")
    with open(info_path, "w") as f:
        f.write(result.source)

def promote_recipe(slug: str, pending_dir: str = PENDING_DIR, recipes_dir: str = RECIPES_DIR):
    """Move a recipe from pending to saved/dinner directory."""
    src = osp.join(pending_dir, slug)
    dst = osp.join(recipes_dir, "dinner", slug)

    if not osp.exists(src):
        raise FileNotFoundError(f"Pending recipe not found: {slug}")

    if osp.exists(dst):
        raise FileExistsError(f"Recipe already exists: {slug}")

    os.makedirs(osp.dirname(dst), exist_ok=True)

    # Move the directory
    shutil.move(src, dst)

def discard_pending(slug: str, pending_dir: str = PENDING_DIR):
    """Delete a pending recipe."""
    recipe_dir = osp.join(pending_dir, slug)
    if not osp.exists(recipe_dir):
        raise FileNotFoundError(f"Pending recipe not found: {slug}")

    shutil.rmtree(recipe_dir)

def demote_recipe(slug: str, recipes_dir: str = RECIPES_DIR, pending_dir: str = PENDING_DIR):
    """Move a recipe from saved to pending."""
    # Find the recipe in saved directories
    src = None
    for recipe in get_all_recipes():
        if recipe.slug == slug:
            src = osp.join(recipes_dir, recipe.path)
            break

    if not src or not osp.exists(src):
        raise FileNotFoundError(f"Saved recipe not found: {slug}")

    dst = osp.join(pending_dir, slug)

    if osp.exists(dst):
        raise FileExistsError(f"Recipe already exists in pending: {slug}")

    os.makedirs(osp.dirname(dst), exist_ok=True)

    # Move the directory
    shutil.move(src, dst)

def delete_saved_recipe(slug: str, recipes_dir: str = RECIPES_DIR):
    """Delete a saved recipe."""
    # Find the recipe in saved directories
    recipe_dir = None
    for recipe in get_all_recipes():
        if recipe.slug == slug:
            recipe_dir = osp.join(recipes_dir, recipe.path)
            break

    if not recipe_dir or not osp.exists(recipe_dir):
        raise FileNotFoundError(f"Saved recipe not found: {slug}")

    shutil.rmtree(recipe_dir)

# Saved recipes are filed under a subdirectory (breakfast/dinner/sides) that's
# an editorial choice, not derivable from category/meal (e.g. sides live
# under sides/ regardless of their meal). Archiving a saved recipe drops a
# marker file naming that subdirectory so unarchiving can put it right back,
# instead of guessing.
_ARCHIVE_ORIGIN_FILE = ".archived_from"

def archive_recipe(slug: str, recipes_dir: str = RECIPES_DIR, pending_dir: str = PENDING_DIR,
                    archived_dir: str = ARCHIVED_DIR):
    """Move a recipe (saved or pending) into the flat archived directory."""
    src = None
    origin_subdir = None
    for recipe in get_all_recipes():
        if recipe.slug == slug:
            src = osp.join(recipes_dir, recipe.path)
            origin_subdir = osp.dirname(recipe.path)
            break
    if not src or not osp.exists(src):
        candidate = osp.join(pending_dir, slug)
        if osp.exists(candidate):
            src = candidate
            origin_subdir = None  # came from pending - no saved subdirectory to remember

    if not src or not osp.exists(src):
        raise FileNotFoundError(f"Recipe not found: {slug}")

    dst = osp.join(archived_dir, slug)

    if osp.exists(dst):
        raise FileExistsError(f"Recipe already exists in archive: {slug}")

    os.makedirs(archived_dir, exist_ok=True)

    # Move the directory
    shutil.move(src, dst)

    if origin_subdir:
        with open(osp.join(dst, _ARCHIVE_ORIGIN_FILE), "w") as f:
            f.write(origin_subdir)

def unarchive_recipe(slug: str, archived_dir: str = ARCHIVED_DIR, recipes_dir: str = RECIPES_DIR):
    """Move a recipe from archived back to saved, restoring its original
    subdirectory (breakfast/dinner/sides) when known, else defaulting to
    dinner/ (matching where newly-promoted recipes land)."""
    src = osp.join(archived_dir, slug)

    if not osp.exists(src):
        raise FileNotFoundError(f"Archived recipe not found: {slug}")

    subdir = "dinner"
    origin_file = osp.join(src, _ARCHIVE_ORIGIN_FILE)
    if osp.exists(origin_file):
        with open(origin_file) as f:
            saved_subdir = f.read().strip()
        if saved_subdir:
            subdir = saved_subdir
        os.remove(origin_file)  # don't carry the marker back into saved/

    dst = osp.join(recipes_dir, subdir, slug)

    if osp.exists(dst):
        raise FileExistsError(f"Recipe already exists: {slug}")

    os.makedirs(osp.dirname(dst), exist_ok=True)

    # Move the directory
    shutil.move(src, dst)

def delete_archived_recipe(slug: str, archived_dir: str = ARCHIVED_DIR):
    """Delete an archived recipe."""
    recipe_dir = osp.join(archived_dir, slug)
    if not osp.exists(recipe_dir):
        raise FileNotFoundError(f"Archived recipe not found: {slug}")

    shutil.rmtree(recipe_dir)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# URL path prefix (under which recipe files are served) and editor status,
# keyed together so the editor's status param maps onto the right routes.
_STATUS_URL_PREFIX = {"saved": "recipes", "pending": "pending", "archived": "archived"}

def _recipe_dir_for_status(status: str, slug: str) -> str | None:
    """Resolve a recipe's directory for the editor, or None if it doesn't exist."""
    if status == "saved":
        recipe = next((r for r in get_all_recipes() if r.slug == slug), None)
        return osp.join(RECIPES_DIR, recipe.path) if recipe else None
    elif status == "pending":
        recipe_dir = osp.join(PENDING_DIR, slug)
        return recipe_dir if osp.exists(recipe_dir) else None
    elif status == "archived":
        recipe_dir = osp.join(ARCHIVED_DIR, slug)
        return recipe_dir if osp.exists(recipe_dir) else None
    return None

def _find_recipe_image(recipe_dir: str) -> str | None:
    """The recipe's photo filename, or None. Prefers image.*, then the local file recipe.md's
    <img> points at (older recipes use names like cajun_chicken_linguine.jpg), then any image."""
    try:
        files = sorted(os.listdir(recipe_dir))
    except OSError:
        return None
    images = [f for f in files if osp.splitext(f)[1].lower() in ALLOWED_IMAGE_EXTENSIONS]
    for f in images:
        if osp.splitext(f)[0].lower() == "image":
            return f
    md_path = osp.join(recipe_dir, "recipe.md")
    if osp.exists(md_path):
        with open(md_path, encoding="utf-8") as fh:
            m = re.search(r'<img\b[^>]*\bsrc=["\']?([^"\'\s>]+)', fh.read(), re.IGNORECASE)
        if m and m.group(1) in images:
            return m.group(1)
    return images[0] if images else None

def _recipe_image_url(status: str, slug: str, filename: str) -> str:
    return f"/{_STATUS_URL_PREFIX[status]}/{slug}/{filename}"

DEFAULT_IMAGE_WIDTH = 400
IMAGE_WIDTH_MIN = 100
IMAGE_WIDTH_MAX = 1200

_IMG_WIDTH_RE = re.compile(r'<img\b[^>]*\bwidth=["\']?(\d+)', re.IGNORECASE)

def _extract_image_width(md_content: str, default: int = DEFAULT_IMAGE_WIDTH) -> int:
    """Read the width= attribute off the recipe's <img> tag, if any."""
    m = _IMG_WIDTH_RE.search(md_content or "")
    return int(m.group(1)) if m else default

_H2_RE = re.compile(r"^##\s+(.*?)\s*:?\s*$", re.MULTILINE)

def _split_recipe_markdown(md_content: str) -> tuple[str, str, bool]:
    """
    Split a recipe.md body into (ingredients_md, instructions_md, matched).

    Content before the first '## ' header (title/servings/img) is discarded —
    the editor always regenerates that part. A header containing "ingredient"
    feeds ingredients_md; one containing "direction"/"instruction"/"step" feeds
    instructions_md. Anything else (or no headers at all) is folded into
    instructions_md with matched=False, so nothing is silently dropped.
    """
    headers = list(_H2_RE.finditer(md_content or ""))
    if not headers:
        return "", (md_content or "").strip(), not (md_content or "").strip()

    ingredients_parts = []
    instructions_parts = []
    matched = True

    for i, h in enumerate(headers):
        title = h.group(1).lower()
        start = h.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(md_content)
        body = md_content[start:end].strip("\n")

        if "ingredient" in title:
            ingredients_parts.append(body)
        elif any(k in title for k in ("direction", "instruction", "step")):
            instructions_parts.append(body)
        else:
            # Unrecognized section — keep it (as its own heading) rather than
            # drop it, but flag so the UI can prompt a manual check.
            instructions_parts.append(f"## {h.group(1)}\n\n{body}")
            matched = False

    return "\n\n".join(p for p in ingredients_parts if p).strip(), \
           "\n\n".join(p for p in instructions_parts if p).strip(), \
           matched

_SERVINGS_LINE_RE = re.compile(r"^Servings:[ \t]*(\d+)?[ \t]*(.*)$", re.MULTILINE | re.IGNORECASE)

def _servings_note(md_content: str) -> str:
    """Free text after the number on the 'Servings: N ...' line of recipe.md."""
    m = _SERVINGS_LINE_RE.search(md_content or "")
    return m.group(2).strip() if m else ""

def _render_recipe_markdown(name: str, servings, image_filename: str | None,
                             ingredients_md: str, instructions_md: str,
                             image_width: int = DEFAULT_IMAGE_WIDTH, servings_note: str = "") -> str:
    """Build a full recipe.md from its structured pieces."""
    note = " ".join((servings_note or "").split())
    lines = [f"# {name}", "", f"Servings: {servings}" + (f" {note}" if note else ""), ""]
    if image_filename:
        lines += [f'<img style="float: right;" src="{image_filename}" width={image_width}>', ""]
    lines += [
        "## Ingredients", "",
        (ingredients_md or "").strip(), "",
        "## Instructions", "",
        (instructions_md or "").strip(), "",
    ]
    return "\n".join(lines)

def _markdown_to_preview_html(md_content: str, status: str, slug: str) -> str:
    """Render recipe markdown to HTML, fixing up relative image paths."""
    html_content = markdown.markdown(md_content, extensions=[
        "tables",
        "fenced_code",
        "nl2br",
        "sane_lists"
    ])
    prefix = _STATUS_URL_PREFIX[status]
    html_content = re.sub(
        r'src="([^":]+)"',
        lambda m: f'src="/{prefix}/{slug}/{m.group(1)}"',
        html_content,
    )
    return html_content

def _rewrite_recipe_image_tag(status: str, slug: str, recipe_dir: str, image_filename: str | None,
                               image_width: int | None = None):
    """
    Re-render recipe.md with an updated (or removed) <img> tag, keeping the
    rest of the file (title/servings from recipe.yaml, existing
    Ingredients/Instructions content) intact. Used after an image is added,
    replaced, removed, or resized so the tag never gets out of sync with the
    file on disk, regardless of what's unsaved in the browser.

    If image_width isn't given, the current width already on disk (or the
    default) is preserved — replacing an image doesn't reset its size.
    """
    yaml_path = osp.join(recipe_dir, "recipe.yaml")
    name = _recipe_name(recipe_dir, slug)
    servings = ""
    if osp.exists(yaml_path):
        try:
            with open(yaml_path) as f:
                loaded = yaml.safe_load(f) or {}
            servings = loaded.get("servings", "")
        except yaml.YAMLError:
            pass

    md_path = osp.join(recipe_dir, "recipe.md")
    ingredients_md, instructions_md, note = "", "", ""
    current_width = DEFAULT_IMAGE_WIDTH
    if osp.exists(md_path):
        with open(md_path) as f:
            existing_md = f.read()
        ingredients_md, instructions_md, _ = _split_recipe_markdown(existing_md)
        current_width = _extract_image_width(existing_md)
        note = _servings_note(existing_md)

    new_md = _render_recipe_markdown(
        name, servings, image_filename, ingredients_md, instructions_md,
        image_width=image_width if image_width is not None else current_width, servings_note=note
    )
    with open(md_path, "w") as f:
        f.write(new_md)
    return new_md

# ---------------------------------------------------------------------------
# Routes — Manage hub
# ---------------------------------------------------------------------------

@app.route("/manage")
def manage_page():
    counts = {
        "saved": len(get_all_recipes()),
        "pending": len(_list_flat_recipes(PENDING_DIR, "pending")),
        "archived": len(_list_flat_recipes(ARCHIVED_DIR, "archived")),
    }
    return render_template("manage.html", active_page="manage", counts=counts,
                           email_enabled=EMAIL_ENABLED, import_enabled=IMPORT_ENABLED)

# ---------------------------------------------------------------------------
# Routes — Recipe chat (Gemini)
# ---------------------------------------------------------------------------

@app.route("/chat")
def chat_page():
    return render_template("chat.html", active_page="chat", chat_enabled=IMPORT_ENABLED,
                           email_enabled=EMAIL_ENABLED, import_enabled=IMPORT_ENABLED)

def _recipe_thumbnail(recipe: Recipe) -> str | None:
    """URL of a saved recipe's photo: image.* if present, else any image file in its folder."""
    name = _find_recipe_image(osp.join(RECIPES_DIR, recipe.path))
    return f"/recipes/{recipe.slug}/{name}" if name else None

def _chat_catalog() -> tuple[str, dict]:
    """Compact catalog of saved recipes for the chat prompt, plus slug -> Recipe."""
    state = _load_state()
    recipes = get_all_recipes()
    _, metas = _get_shopping_list_data()
    entries = []
    for r in recipes:
        meta = metas.get(r.slug)
        entries.append({
            "slug": r.slug,
            "name": meta.name if meta else r.name,
            "category": r.category,
            "meal": r.meal,
            "ingredients": [i.food for i in meta.ingredients] if meta else [],
            "last_used": state.get(r.slug, {}).get("last_used_date"),
            "selected": r.selected,
        })
    return build_catalog(entries), {r.slug: r for r in recipes}

@app.route("/chat/message", methods=["POST"])
def chat_message():
    if not IMPORT_ENABLED:
        return jsonify({"error": "Chat needs GEMINI_API_KEY to be set on the server."}), 503
    body = request.get_json(silent=True) or {}
    messages = body.get("messages") or []
    catalog, by_slug = _chat_catalog()
    try:
        if str(body.get("search") or "").strip():
            # "Look for new recipes" button: the query came with the offer, skip a model turn.
            result = ChatReply(reply="Here are some recipes from around the web:",
                               web_search=str(body["search"]).strip()[:200])
        else:
            result = recipe_chat(messages, catalog, api_key=GEMINI_API_KEY)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Chat request failed")
        return jsonify({"error": friendly_error(e)}), 502

    picks, seen = [], set()
    for pick in result.recipes:
        recipe = by_slug.get(pick.slug)
        if recipe and pick.slug not in seen:
            seen.add(pick.slug)
            picks.append({"slug": recipe.slug, "name": recipe.name, "reason": pick.reason,
                          "selected": recipe.selected, "image_url": _recipe_thumbnail(recipe),
                          "missing": pick.missing[:12], "key_ingredients": pick.key_ingredients[:8]})

    web = []
    if result.web_search:
        try:
            web = [r.model_dump() for r in web_recipe_search(result.web_search, exclude=[r.name for r in by_slug.values()])]
        except Exception as e:
            logger.exception("Web recipe search failed")
            result.reply += f"\n\n(The web search failed: {friendly_error(e)})"
        if result.web_search and not web and "search failed" not in result.reply:
            result.reply += "\n\nI couldn't find recipe pages for that. Try describing it differently."

    return jsonify({
        "reply": result.reply,
        "reply_html": markdown.markdown(html_escape(result.reply), extensions=["sane_lists", "nl2br"]),
        "recipes": picks,
        "offer_search": result.offer_search and not result.web_search,
        "offer_query": result.offer_query,
        "web_query": result.web_search,
        "web_recipes": web,
    })

def web_recipe_search(query: str, exclude: list[str] | None = None):
    """Real recipe pages for `query` (Gemini + Google Search). Patched in tests."""
    return search_recipes(query, make_client(GEMINI_API_KEY), exclude=exclude)

# ---------------------------------------------------------------------------
# Routes — Recipe Editor
# ---------------------------------------------------------------------------

@app.route("/editor", methods=["GET"])
def editor_page():
    """Editing lives on the Recipes page now; keep old links working."""
    slug, status = request.args.get("edit"), request.args.get("status", "saved")
    if slug:
        return redirect(url_for("recipes_list", recipe=slug, status=status, edit=1))
    return redirect(url_for("recipes_list", status=request.args.get("tab", "saved")))

def _list_flat_recipes(dir_path: str, status: str) -> list[dict]:
    """List recipes for a flat (non-meal-nested) directory, e.g. pending/archived."""
    recipes = []
    if osp.exists(dir_path):
        for slug in os.listdir(dir_path):
            recipe_dir = osp.join(dir_path, slug)
            if osp.isdir(recipe_dir):
                category, meal = _load_category_meal(recipe_dir, slug)
                recipes.append({
                    "slug": slug,
                    "name": _recipe_name(recipe_dir, slug),
                    "category": category,
                    "meal": meal,
                    "status": status
                })
    return recipes

@app.route("/editor/recipes", methods=["GET"])
def list_all_recipes():
    """List all recipes (saved, pending, and archived) for the editor."""
    saved_recipes = [
        {
            "slug": recipe.slug,
            "name": recipe.name,
            "path": recipe.path,
            "category": recipe.category,
            "meal": recipe.meal,
            "status": "saved"
        }
        for recipe in get_all_recipes()
    ]

    return jsonify({
        "success": True,
        "saved": saved_recipes,
        "pending": _list_flat_recipes(PENDING_DIR, "pending"),
        "archived": _list_flat_recipes(ARCHIVED_DIR, "archived")
    })

DEFAULT_CATEGORY = CategoryType.Entree.value
DEFAULT_MEAL = MealType.Dinner.value

@app.route("/editor/foods", methods=["GET"])
def list_known_foods():
    """Sorted list of known food names, for the ingredient autocomplete."""
    return jsonify({"success": True, "foods": sorted(f.get_name() for f in list_foods())})

@app.route("/editor/recipe/<status>/<slug>", methods=["GET"])
def load_recipe(status, slug):
    """Load a recipe's metadata and content, structured for the editor form."""
    if status not in ("saved", "pending", "archived"):
        return jsonify({"error": "Invalid status"}), 400

    recipe_dir = _recipe_dir_for_status(status, slug)
    if not recipe_dir:
        return jsonify({"error": "Recipe not found"}), 404

    # Load recipe.yaml leniently — defaults fill in anything missing or
    # invalid so even a broken file can be opened and fixed in the editor.
    yaml_path = osp.join(recipe_dir, "recipe.yaml")
    yaml_error = None
    raw = {}
    if osp.exists(yaml_path):
        try:
            with open(yaml_path) as f:
                raw = yaml.safe_load(f) or {}
            if not isinstance(raw, dict):
                raise yaml.YAMLError(f"Expected a YAML mapping, got {type(raw).__name__}")
        except yaml.YAMLError as e:
            yaml_error = str(e)
            raw = {}

    metadata = {
        "name": _recipe_name(recipe_dir, slug),
        "servings": raw.get("servings", 1),
        "category": str(raw.get("category", DEFAULT_CATEGORY)).upper(),
        "meal": str(raw.get("meal", DEFAULT_MEAL)).upper(),
        "enabled": raw.get("enabled", True),
        "min_period_weeks": raw.get("min_period_weeks", 4),
        "ingredients": [
            {"food": str(ing.get("food", "")), "quantity": str(ing.get("quantity") or "")}
            for ing in (raw.get("ingredients") or []) if isinstance(ing, dict)
        ],
    }

    # Load recipe.md (try recipe.md first, then any .md file) and split it
    md_content = ""
    md_path = osp.join(recipe_dir, "recipe.md")
    if not osp.exists(md_path):
        for f in os.listdir(recipe_dir):
            if f.endswith(".md"):
                md_path = osp.join(recipe_dir, f)
                break
    if osp.exists(md_path):
        with open(md_path, "r") as f:
            md_content = f.read()

    ingredients_md, instructions_md, markdown_matched = _split_recipe_markdown(md_content)
    metadata["servings_note"] = _servings_note(md_content)

    image_filename = _find_recipe_image(recipe_dir)
    image_url = _recipe_image_url(status, slug, image_filename) if image_filename else None
    image_width = _extract_image_width(md_content)

    return jsonify({
        "success": True,
        "metadata": metadata,
        "yaml_error": yaml_error,
        "ingredients_md": ingredients_md,
        "instructions_md": instructions_md,
        "markdown_matched": markdown_matched,
        "image_filename": image_filename,
        "image_url": image_url,
        "image_width": image_width,
        "preview_html": _markdown_to_preview_html(md_content, status, slug) if md_content else ""
    })

def _validate_recipe_form(data: dict) -> tuple[dict | None, str | None]:
    """Recipe form state (editor, import review) -> (recipe.yaml dict, error message)."""
    name = (data.get("name") or "").strip()
    if not name:
        return None, "Name is required"
    try:
        servings = int(data.get("servings") or 1)
        min_period_weeks = int(data.get("min_period_weeks", 4) or 0)
        if servings < 0 or min_period_weeks < 0:
            raise ValueError
    except (TypeError, ValueError):
        return None, "Servings and repeat weeks must be non-negative numbers"

    category = str(data.get("category", "")).upper()
    if category not in (c.value for c in CategoryType):
        return None, f"Invalid category: {category}"
    meal = str(data.get("meal", "")).upper()
    if meal not in (m.value for m in MealType):
        return None, f"Invalid meal: {meal}"

    ingredients = []
    for row in data.get("ingredients", []):
        food = (row.get("food") or "").strip()
        if not food:
            continue
        quantity = (row.get("quantity") or "").strip()
        if quantity == "-":
            quantity = ""
        try:
            parse_quantity(quantity)
        except ValueError as e:
            return None, f"Ingredient '{food}': {e}"
        ingredients.append({"food": food, "quantity": quantity})

    return {
        "name": name,
        "servings": servings,
        "category": category,
        "meal": meal,
        "enabled": bool(data.get("enabled", True)),
        "min_period_weeks": min_period_weeks,
        "ingredients": ingredients,
    }, None

def _write_recipe(recipe_dir: str, yaml_data: dict, ingredients_md: str, instructions_md: str,
                  servings_note: str = "") -> str:
    """Write recipe.yaml and a regenerated recipe.md. Returns the markdown."""
    os.makedirs(recipe_dir, exist_ok=True)
    with open(osp.join(recipe_dir, "recipe.yaml"), "w") as f:
        yaml.safe_dump(yaml_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Keep the current image width; it's managed by the dedicated width control.
    md_path = osp.join(recipe_dir, "recipe.md")
    width = DEFAULT_IMAGE_WIDTH
    if osp.exists(md_path):
        with open(md_path) as f:
            width = _extract_image_width(f.read())
    md_content = _render_recipe_markdown(
        yaml_data["name"], yaml_data["servings"], _find_recipe_image(recipe_dir),
        ingredients_md or "", instructions_md or "", image_width=width, servings_note=servings_note)
    with open(md_path, "w") as f:
        f.write(md_content)
    return md_content

@app.route("/editor/recipe/<status>/<slug>", methods=["POST"])
def save_recipe(status, slug):
    """Save a recipe's metadata (recipe.yaml) and content (recipe.md)."""
    if status not in ("saved", "pending", "archived"):
        return jsonify({"error": "Invalid status"}), 400
    recipe_dir = _recipe_dir_for_status(status, slug)
    if not recipe_dir:
        return jsonify({"error": "Recipe not found"}), 404

    data = request.get_json() or {}
    yaml_data, error = _validate_recipe_form(data)
    if error:
        return jsonify({"error": error}), 400
    try:
        md_content = _write_recipe(recipe_dir, yaml_data, data.get("ingredients_md", ""),
                                   data.get("instructions_md", ""), data.get("servings_note", ""))
    except Exception as e:
        logger.error("Failed to save recipe: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500

    if status == "saved":
        _invalidate_shopping_list_cache()
    return jsonify({
        "success": True,
        "message": "Recipe saved successfully",
        "preview_html": _markdown_to_preview_html(md_content, status, slug)
    })

@app.route("/editor/recipe/<status>/<slug>/image", methods=["POST"])
def upload_recipe_image(status, slug):
    """Add or replace the recipe's image."""
    recipe_dir = _recipe_dir_for_status(status, slug)
    if not recipe_dir:
        return jsonify({"error": "Recipe not found"}), 404

    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"error": "No image file provided"}), 400

    ext = osp.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": f"Unsupported image type: {ext or '(none)'}"}), 400

    try:
        # Remove any existing image (in case the extension changed)
        existing = _find_recipe_image(recipe_dir)
        if existing:
            os.remove(osp.join(recipe_dir, existing))

        filename = f"image{ext}"
        file.save(osp.join(recipe_dir, filename))
        new_md = _rewrite_recipe_image_tag(status, slug, recipe_dir, filename)

        return jsonify({
            "success": True,
            "filename": filename,
            "url": _recipe_image_url(status, slug, filename),
            "image_width": _extract_image_width(new_md),
            "preview_html": _markdown_to_preview_html(new_md, status, slug)
        })
    except Exception as e:
        logger.error("Failed to save recipe image: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/editor/recipe/<status>/<slug>/image/width", methods=["POST"])
def set_recipe_image_width(status, slug):
    """Adjust the display width of the recipe's <img> tag."""
    recipe_dir = _recipe_dir_for_status(status, slug)
    if not recipe_dir:
        return jsonify({"error": "Recipe not found"}), 404

    try:
        width = int((request.get_json() or {}).get("width"))
    except (TypeError, ValueError):
        return jsonify({"error": "Width must be a number"}), 400

    if not (IMAGE_WIDTH_MIN <= width <= IMAGE_WIDTH_MAX):
        return jsonify({"error": f"Width must be between {IMAGE_WIDTH_MIN} and {IMAGE_WIDTH_MAX}"}), 400

    image_filename = _find_recipe_image(recipe_dir)
    if not image_filename:
        return jsonify({"error": "No image to resize"}), 404

    try:
        new_md = _rewrite_recipe_image_tag(status, slug, recipe_dir, image_filename, image_width=width)
        return jsonify({
            "success": True,
            "width": width,
            "preview_html": _markdown_to_preview_html(new_md, status, slug)
        })
    except Exception as e:
        logger.error("Failed to set recipe image width: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/editor/recipe/<status>/<slug>/image", methods=["DELETE"])
def delete_recipe_image(status, slug):
    """Remove the recipe's image, if any."""
    recipe_dir = _recipe_dir_for_status(status, slug)
    if not recipe_dir:
        return jsonify({"error": "Recipe not found"}), 404

    existing = _find_recipe_image(recipe_dir)
    if not existing:
        return jsonify({"error": "No image found"}), 404

    try:
        os.remove(osp.join(recipe_dir, existing))
        new_md = _rewrite_recipe_image_tag(status, slug, recipe_dir, None)
        return jsonify({
            "success": True,
            "preview_html": _markdown_to_preview_html(new_md, status, slug)
        })
    except Exception as e:
        logger.error("Failed to delete recipe image: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/editor/preview", methods=["POST"])
def preview_markdown():
    """Render markdown to HTML for preview."""
    data = request.get_json()
    markdown_content = data.get("markdown", "")
    recipe_slug = data.get("slug", "")

    html_content = markdown.markdown(markdown_content, extensions=[
        "tables",
        "fenced_code",
        "nl2br",
        "sane_lists"
    ])

    # Fix image paths if recipe slug is provided
    if recipe_slug:
        # Find the recipe to get its path
        recipes = get_all_recipes()
        recipe = next((r for r in recipes if r.slug == recipe_slug), None)

        if recipe:
            # Fix relative image paths
            html_content = re.sub(
                r'src="([^":]+)"',
                lambda m: f'src="/recipes/{recipe.slug}/{m.group(1)}"',
                html_content,
            )
        else:
            # Check if it's a pending recipe
            pending_dir = osp.join(PENDING_DIR, recipe_slug)
            if osp.exists(pending_dir):
                html_content = re.sub(
                    r'src="([^":]+)"',
                    lambda m: f'src="/pending/{recipe_slug}/{m.group(1)}"',
                    html_content,
                )

    return jsonify({
        "success": True,
        "html": html_content
    })

# ---------------------------------------------------------------------------
# Routes — Recipe Import (Gemini)
# ---------------------------------------------------------------------------

@app.route("/import", methods=["GET"])
def import_page():
    """Render the Import Recipe page."""
    return render_template("import.html", active_page="import", email_enabled=EMAIL_ENABLED, import_enabled=IMPORT_ENABLED)

# ---------------------------------------------------------------------------
# Import jobs — extraction runs in a background thread (it makes several
# sequential Gemini calls as it retries against validation errors, which can
# take a while) so the web UI can poll for progress instead of blocking on
# one long request.
# ---------------------------------------------------------------------------

IMPORT_JOBS: dict[str, dict] = {}
IMPORT_JOBS_LOCK = threading.Lock()
IMPORT_JOB_TTL_SECONDS = 3600
MAX_IMPORT_IMAGES = 6
MAX_IMPORT_IMAGE_BYTES = 15_000_000

def _prune_import_jobs():
    """Drop jobs older than IMPORT_JOB_TTL_SECONDS so IMPORT_JOBS doesn't grow unbounded."""
    cutoff = time.time() - IMPORT_JOB_TTL_SECONDS
    with IMPORT_JOBS_LOCK:
        for job_id in [jid for jid, job in IMPORT_JOBS.items() if job["created_at"] < cutoff]:
            del IMPORT_JOBS[job_id]

_MD_IMAGE_RE = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']|!\[[^\]]*\]\(([^)\s]+)', re.IGNORECASE)

def _draft_from_import(result: ImportResult) -> dict:
    """Imported recipe -> the recipe form state used by the editor and import review."""
    data = result.recipe_data.model_dump(mode="json")
    ingredients_md, instructions_md, _ = _split_recipe_markdown(result.markdown)
    m = _MD_IMAGE_RE.search(result.markdown or "")
    image_url = (m.group(1) or m.group(2)) if m else None
    return {
        "name": data["name"], "servings": data["servings"], "category": data["category"],
        "meal": data["meal"], "enabled": data.get("enabled", True),
        "min_period_weeks": data.get("min_period_weeks", 4),
        "ingredients": [{"food": i["food"], "quantity": i.get("quantity", "")} for i in data["ingredients"]],
        "ingredients_md": ingredients_md, "instructions_md": instructions_md,
        "servings_note": _servings_note(result.markdown),
        "image_url": image_url if image_url and image_url.startswith(("http://", "https://")) else None,
        "source": result.source,
    }

def _download_recipe_image(url: str, recipe_dir: str) -> str | None:
    """Save a recipe page's photo as image.<ext>. Best effort: None on any failure."""
    try:
        import requests as _requests
        res = _requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0 (Pantry recipe import)"})
        ctype = res.headers.get("Content-Type", "").split(";")[0].strip()
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(ctype)
        if res.status_code != 200 or not ext or len(res.content) > 15_000_000:
            return None
        name = f"image{ext}"
        with open(osp.join(recipe_dir, name), "wb") as f:
            f.write(res.content)
        return name
    except Exception as e:
        logger.info("Could not download recipe image %s: %s", url[:80], e)
        return None

def _saved_subdir(yaml_data: dict) -> str:
    """Folder under saved/ for a new recipe, matching the existing layout."""
    if yaml_data["meal"] == "BREAKFAST":
        return "breakfast"
    if yaml_data["category"] == "SIDE":
        return "sides"
    return "dinner"

def _slug_taken(slug: str) -> bool:
    return (any(r.slug == slug for r in get_all_recipes())
            or osp.exists(osp.join(PENDING_DIR, slug)) or osp.exists(osp.join(ARCHIVED_DIR, slug)))

def _run_import_job(job_id: str, url: str | None, text: str | None,
                    images: list[tuple[bytes, str]] | None = None):
    """Background-thread target: run extract_recipe(), recording progress events and the final outcome on the job."""
    def on_progress(event: dict):
        with IMPORT_JOBS_LOCK:
            job = IMPORT_JOBS.get(job_id)
            if job is not None:
                job["events"].append(event)

    try:
        result = extract_recipe(url=url, text=text, images=images, on_progress=on_progress)
    except Exception as e:
        logger.error("Import job %s failed: %s", job_id, e)
        with IMPORT_JOBS_LOCK:
            job = IMPORT_JOBS.get(job_id)
            if job is not None:
                job["status"] = "error"
                job["error"] = str(e)
        return

    with IMPORT_JOBS_LOCK:
        job = IMPORT_JOBS.get(job_id)
        if job is not None:
            job["status"] = "done"
            job["result"] = {
                "recipe": result.recipe_data.model_dump(mode="json"),
                "markdown_preview": result.markdown,
                "slug": result.slug,
                "source": result.source,
                "draft": _draft_from_import(result),
                "validation_errors": [{"field": e.field, "message": e.message} for e in (result.validation_errors or [])],
            }

@app.route("/import/extract", methods=["POST"])
def import_extract():
    """Start a background Gemini extraction job and return its job_id; poll /import/status/<job_id> for progress/result."""
    if not IMPORT_ENABLED:
        return jsonify({
            "error": "Recipe import disabled. Set GEMINI_API_KEY environment variable to enable."
        }), 503

    # JSON {url, text}, or multipart form with `images` files and an optional `text` note.
    images = []
    if request.files:
        data = request.form
        files = request.files.getlist("images")
        if len(files) > MAX_IMPORT_IMAGES:
            return jsonify({"error": f"Up to {MAX_IMPORT_IMAGES} photos at a time."}), 400
        for f in files:
            if not (f.mimetype or "").startswith("image/"):
                return jsonify({"error": f"{f.filename or 'File'} is not an image."}), 400
            blob = f.read()
            if len(blob) > MAX_IMPORT_IMAGE_BYTES:
                return jsonify({"error": f"{f.filename or 'Photo'} is too large (max {MAX_IMPORT_IMAGE_BYTES // 1_000_000} MB)."}), 400
            images.append((blob, f.mimetype))
    else:
        data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip() or None
    text = (data.get("text") or "").strip() or None

    if not url and not text and not images:
        return jsonify({"error": "Provide a URL, pasted text, or a photo."}), 400

    _prune_import_jobs()

    job_id = uuid.uuid4().hex
    with IMPORT_JOBS_LOCK:
        IMPORT_JOBS[job_id] = {
            "status": "running",
            "events": [],
            "max_attempts": MAX_RETRIES,
            "created_at": time.time(),
        }

    threading.Thread(target=_run_import_job, args=(job_id, url, text, images or None), daemon=True).start()

    return jsonify({"success": True, "job_id": job_id, "max_attempts": MAX_RETRIES})

@app.route("/import/status/<job_id>")
def import_status(job_id):
    """Poll the progress (and, once finished, result) of a background extraction job started by /import/extract."""
    with IMPORT_JOBS_LOCK:
        job = IMPORT_JOBS.get(job_id)
        if job is None:
            return jsonify({"error": "Unknown or expired import job"}), 404

        response = {
            "status": job["status"],
            "events": job["events"],
            "max_attempts": job["max_attempts"],
        }
        if job["status"] == "done":
            response["result"] = job["result"]
        elif job["status"] == "error":
            response["error"] = job["error"]

    if job["status"] == "done":
        # Stash for /import/confirm, same as the old synchronous flow.
        result = job["result"]
        session["pending_import"] = {
            "recipe_data": result["recipe"],
            "markdown": result["markdown_preview"],
            "slug": result["slug"],
            "source": result["source"],
        }
        session["pending_import_job_id"] = job_id

    return jsonify(response)

@app.route("/import/confirm", methods=["POST"])
def import_confirm():
    """Save a reviewed import. JSON {draft, destination: 'saved'|'pending'}; the draft is the
    recipe form state (possibly edited). Without a draft, saves the last extraction as-is."""
    body = request.get_json(silent=True) or {}
    draft = body.get("draft")
    destination = body.get("destination", "pending")
    if destination not in ("saved", "pending"):
        return jsonify({"error": "destination must be 'saved' or 'pending'"}), 400

    if draft is None:
        pending = session.get("pending_import")
        if not pending:
            return jsonify({"error": "No pending import found. Please extract first."}), 400
        draft = _draft_from_import(ImportResult(
            recipe_data=RecipeData(**pending["recipe_data"]), markdown=pending["markdown"],
            slug=pending["slug"], source=pending["source"]))

    yaml_data, error = _validate_recipe_form(draft)
    if error:
        return jsonify({"error": error}), 400

    from recipe_core.gemini_importer import _generate_slug
    slug = _generate_slug(yaml_data["name"])
    if _slug_taken(slug):
        return jsonify({"error": f"A recipe named '{yaml_data['name']}' already exists. Rename it first."}), 409

    recipe_dir = (osp.join(RECIPES_DIR, _saved_subdir(yaml_data), slug) if destination == "saved"
                  else osp.join(PENDING_DIR, slug))
    try:
        os.makedirs(recipe_dir)
        if draft.get("image_url"):
            _download_recipe_image(draft["image_url"], recipe_dir)
        _write_recipe(recipe_dir, yaml_data, draft.get("ingredients_md", ""), draft.get("instructions_md", ""),
                      draft.get("servings_note", ""))
        with open(osp.join(recipe_dir, "source.txt"), "w") as f:
            f.write(str(draft.get("source") or (session.get("pending_import") or {}).get("source") or "import"))
    except Exception as e:
        logger.error("Failed to save imported recipe: %s", e, exc_info=True)
        shutil.rmtree(recipe_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500

    if destination == "saved":
        _invalidate_shopping_list_cache()
    session.pop("pending_import", None)
    job_id = session.pop("pending_import_job_id", None)
    if job_id:
        with IMPORT_JOBS_LOCK:
            IMPORT_JOBS.pop(job_id, None)
    return jsonify({"success": True, "slug": slug, "status": destination})

# ---------------------------------------------------------------------------
# Routes — AI recipe revision (editor and import review)
# ---------------------------------------------------------------------------

@app.route("/recipe/revise", methods=["POST"])
def recipe_revise():
    """{draft, instruction, history?} -> {draft, note}. Stateless: the client holds the draft."""
    if not IMPORT_ENABLED:
        return jsonify({"error": "AI editing needs GEMINI_API_KEY to be set on the server."}), 503
    body = request.get_json(silent=True) or {}
    instruction = str(body.get("instruction") or "").strip()
    if not instruction:
        return jsonify({"error": "Say what to change."}), 400
    try:
        revised = revise_recipe(body.get("draft") or {}, instruction,
                                history=body.get("history") or [], api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.exception("Recipe revision failed")
        return jsonify({"error": friendly_error(e)}), 502
    return jsonify({"success": True, **revised})

# @app.route("/import/extract", methods=["POST"])
# def import_extract():
#     """Step 1: extract recipe via Claude and return a preview."""
#     data = request.get_json()
#     url  = (data.get("url")  or "").strip() or None
#     text = (data.get("text") or "").strip() or None

#     if not url and not text:
#         return jsonify({"error": "Provide a URL or pasted text."}), 400

#     try:
#         result = extract_recipe(url=url, text=text)
#     except Exception as e:
#         logger.error("Extraction failed: %s", e)
#         return jsonify({"error": str(e)}), 500

#     session["pending_import"] = {
#         "recipe_data": result.recipe_data.model_dump(mode="json"),
#         "markdown":    result.markdown,
#         "slug":        result.slug,
#         "source":      result.source,
#     }

#     return jsonify({
#         "recipe":           result.recipe_data.model_dump(mode="json"),
#         "markdown_preview": result.markdown,
#         "slug":             result.slug,
#         "source":           result.source,
#     })

# @app.route("/import/confirm", methods=["POST"])
# def import_confirm():
#     """Step 2: save the previewed recipe to pending/."""
#     pending = session.get("pending_import")
#     if not pending:
#         return jsonify({"error": "No pending import found. Please extract first."}), 400

#     result = ImportResult(
#         recipe_data=RecipeData(**pending["recipe_data"]),
#         markdown=pending["markdown"],
#         slug=pending["slug"],
#         source=pending["source"],
#     )

#     try:
#         save_pending(result, pending_dir=PENDING_DIR)
#     except Exception as e:
#         logger.error("Failed to save pending recipe: %s", e)
#         return jsonify({"error": str(e)}), 500

#     session.pop("pending_import", None)
#     return jsonify({"success": True, "slug": result.slug})

# ---------------------------------------------------------------------------
# Routes — Edit Ingredients (foods.yaml registry)
# ---------------------------------------------------------------------------

@app.route("/ingredients", methods=["GET"])
def ingredients_page():
    """Render the Edit Ingredients page."""
    return render_template(
        "ingredients.html",
        active_page="ingredients",
        email_enabled=EMAIL_ENABLED,
        import_enabled=IMPORT_ENABLED,
        categories=[c.value for c in FoodType],
    )

@app.route("/ingredients/list", methods=["GET"])
def list_ingredients():
    """JSON list of every food in the registry, for the Edit Ingredients page."""
    return jsonify({
        "success": True,
        "foods": [f.model_dump(mode="json") for f in list_foods()],
    })

@app.route("/ingredients", methods=["POST"])
def create_ingredient():
    """Add a new food to the registry."""
    data = request.get_json() or {}
    try:
        food = create_food(data)
    except ValidationError as e:
        return jsonify({"error": e.errors()[0]["msg"]}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    _invalidate_shopping_list_cache()
    return jsonify({"success": True, "food": food.model_dump(mode="json")})

@app.route("/ingredients/<name>", methods=["POST"])
def update_ingredient(name):
    """Update the food currently named `name` (its primary/first alias)."""
    data = request.get_json() or {}
    try:
        food = update_food(name, data)
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except ValidationError as e:
        return jsonify({"error": e.errors()[0]["msg"]}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    _invalidate_shopping_list_cache()
    return jsonify({"success": True, "food": food.model_dump(mode="json")})

@app.route("/ingredients/delete/<name>", methods=["POST"])
def delete_ingredient(name):
    """Delete the food named `name` (its primary/first alias) from the registry."""
    try:
        delete_food(name)
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    _invalidate_shopping_list_cache()
    return jsonify({"success": True})

# ---------------------------------------------------------------------------
# Routes — pending recipes
# ---------------------------------------------------------------------------

@app.route("/pending")
def pending_list():
    """Redirect to editor page."""
    return redirect("/editor")

@app.route("/pending/promote/<slug>", methods=["POST"])
def promote(slug):
    try:
        promote_recipe(slug, pending_dir=PENDING_DIR, recipes_dir=RECIPES_DIR)
        _invalidate_shopping_list_cache()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

@app.route("/pending/discard/<slug>", methods=["POST"])
def discard(slug):
    try:
        discard_pending(slug, pending_dir=PENDING_DIR)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

@app.route("/editor/demote/<slug>", methods=["POST"])
def demote(slug):
    """Move a recipe from saved to pending."""
    try:
        demote_recipe(slug, recipes_dir=RECIPES_DIR, pending_dir=PENDING_DIR)
        _invalidate_shopping_list_cache()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

@app.route("/editor/delete/<slug>", methods=["POST"])
def delete_saved(slug):
    """Delete a saved recipe."""
    try:
        delete_saved_recipe(slug, recipes_dir=RECIPES_DIR)
        _invalidate_shopping_list_cache()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

@app.route("/editor/archive/<slug>", methods=["POST"])
def archive(slug):
    """Move a recipe (saved or pending) to the archive."""
    try:
        archive_recipe(slug, recipes_dir=RECIPES_DIR, pending_dir=PENDING_DIR, archived_dir=ARCHIVED_DIR)
        _invalidate_shopping_list_cache()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

@app.route("/editor/unarchive/<slug>", methods=["POST"])
def unarchive(slug):
    """Restore an archived recipe to saved."""
    try:
        unarchive_recipe(slug, archived_dir=ARCHIVED_DIR, recipes_dir=RECIPES_DIR)
        _invalidate_shopping_list_cache()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

@app.route("/editor/delete_archived/<slug>", methods=["POST"])
def delete_archived(slug):
    """Delete an archived recipe."""
    try:
        delete_archived_recipe(slug, archived_dir=ARCHIVED_DIR)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})

# ---------------------------------------------------------------------------
# Routes — schedule management
# ---------------------------------------------------------------------------

def _next_plan_run(config: dict) -> str | None:
    if not config["enabled"]:
        return None
    job = scheduler.get_job("weekly_shopping_list")
    nxt = job.next_run_time if job else None
    return nxt.strftime("%a %b %-d, %-I:%M %p") if nxt else None

@app.route("/plan")
def plan_page():
    return render_template("plan.html", active_page="plan", email_enabled=EMAIL_ENABLED,
                           import_enabled=IMPORT_ENABLED)

@app.route("/schedule/config", methods=["GET"])
def get_schedule():
    config = _get_schedule_config()
    last = _load_state().get("_week_plan")
    return jsonify({"success": True, "config": config, "next_run": _next_plan_run(config),
                    "last_plan": last, "email_enabled": EMAIL_ENABLED,
                    "devices": len(PUSH.subscriptions())})

@app.route("/schedule/config", methods=["POST"])
def save_schedule():
    data = request.get_json(silent=True) or {}
    try:
        hour, minute = map(int, str(data.get("send_time", "09:00")).split(":"))
        config = {
            "enabled": bool(data.get("enabled")),
            "num_recipes": max(1, min(14, int(data.get("num_recipes", 3)))),
            "frequency_weeks": 2 if int(data.get("frequency_weeks", 1)) == 2 else 1,
            "day_of_week": int(data.get("day_of_week", 6)) % 7,
            "send_time": f"{hour % 24:02d}:{minute % 60:02d}",
            "fresh_start": bool(data.get("fresh_start", True)),
            "notify": bool(data.get("notify", True)),
            "send_email": bool(data.get("send_email")),
            "recipients": str(data.get("recipients", "")).strip(),
        }
    except (TypeError, ValueError) as e:
        return jsonify({"success": False, "error": f"Invalid settings: {e}"}), 400
    _save_schedule_config(config)
    _reschedule_email_job()
    return jsonify({"success": True, "config": config, "next_run": _next_plan_run(config)})

@app.route("/schedule/send_now", methods=["POST"])
def send_now():
    """Run the weekly plan immediately (pick, select, notify, email)."""
    try:
        return jsonify({"success": True, **run_weekly_plan(force=True)})
    except Exception as e:
        logger.error("Weekly plan failed: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

# ---------------------------------------------------------------------------
# Routes — push notifications
# ---------------------------------------------------------------------------

@app.route("/push/key")
def push_key():
    return jsonify({"public_key": PUSH.public_key})

@app.route("/push/subscribe", methods=["POST"])
def push_subscribe():
    data = request.get_json(silent=True) or {}
    try:
        PUSH.add(data.get("subscription") or {}, label=str(data.get("label", "")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, "devices": len(PUSH.subscriptions())})

@app.route("/push/unsubscribe", methods=["POST"])
def push_unsubscribe():
    PUSH.remove(str((request.get_json(silent=True) or {}).get("endpoint", "")))
    return jsonify({"success": True, "devices": len(PUSH.subscriptions())})

@app.route("/push/status", methods=["POST"])
def push_status():
    endpoint = str((request.get_json(silent=True) or {}).get("endpoint", ""))
    return jsonify({"subscribed": PUSH.has(endpoint), "devices": len(PUSH.subscriptions())})

@app.route("/push/test", methods=["POST"])
def push_test():
    sent = PUSH.send_all("Pantry", "Notifications are working.", url="/plan", tag="test")
    return jsonify({"success": sent > 0, "sent": sent})

# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------

scheduler = BackgroundScheduler()
scheduler.start()

def _reschedule_email_job():
    """Remove existing job and reschedule based on current config."""
    # Remove existing job if it exists
    if scheduler.get_job("weekly_shopping_list"):
        scheduler.remove_job("weekly_shopping_list")

    config = _get_schedule_config()
    if not config.get("enabled"):
        logger.info("Weekly plan disabled")
        return

    day_of_week = config.get("day_of_week", 0)
    send_time = config.get("send_time", "09:00")
    hour, minute = map(int, send_time.split(":"))

    # Schedule job using cron trigger
    trigger = CronTrigger(
        day_of_week=day_of_week,
        hour=hour,
        minute=minute
    )

    scheduler.add_job(
        func=_scheduled_weekly_plan,
        trigger=trigger,
        id="weekly_shopping_list",
        name="Weekly plan",
        replace_existing=True
    )

    logger.info("Scheduled weekly plan for day=%d at %s", day_of_week, send_time)

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    os.makedirs(PENDING_DIR, exist_ok=True)

    # Initialize scheduler with current config
    _reschedule_email_job()

    try:
        app.run(
            host=os.environ.get("RECIPES_HOST", "0.0.0.0"),
            port=int(os.environ.get("RECIPES_PORT", "5000")),
            debug=os.environ.get("RECIPES_DEBUG", "1") == "1",
        )
    finally:
        scheduler.shutdown()
