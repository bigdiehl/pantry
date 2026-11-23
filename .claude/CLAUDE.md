# Pantry

Personal recipe app: browse recipes, build a shopping list, weekly auto-pick with phone reminders, Gemini import (URL/text/photo) and recipe chat. Mobile-first PWA.

## Quick Reference

**Stack:** Flask (Python 3.11+), Pint, Pydantic, google-genai, pywebpush, WeasyPrint, APScheduler. Bootstrap 5 + plain JS, no build step.

**Structure:**
- `recipe_core/` - Domain logic, no Flask (models, shopping list, foods, importer, chat, push, mailer)
- `web/` - Flask app (`app.py`), templates, static (vendored libs in `static/vendor/`)
- Recipe data: separate repo `../diehl_recipes` (override `RECIPES_DATA_DIR`): `recipes/{saved,pending,archived}/`
- `scripts/` - Service install, auto-update, data backup, Tailscale HTTPS, icons
- `tests/` - pytest (fixtures from `recipe_core/test/`); external services always mocked
- `docs/` - Developer design docs (start at `docs/README.md`)
- `working/` - TODO and notes

**Run:** `set -a; . ./.env; set +a; uv run web/app.py` (localhost:5000; `.env` is git-ignored, optional)

**Test:** `uv run pytest`. CI: `.github/workflows/ci.yml`

**Server:** `frank.local` (Debian, ssh). `pantry.service`, `pantry-update.timer` (pull/test/deploy every 5 min; `sudo systemctl start pantry-update` to deploy now), `pantry-backup.timer` (weekly commit+push of recipe edits). App at `https://frank.<tailnet>.ts.net`. See `docs/DEPLOYMENT.md`.

## Pages

`/` shopping list, `/recipes_list` recipes (browse + Edit mode; Saved/Pending/Archived), `/chat`, `/manage` -> `/plan` (weekly plan), `/import`, `/ingredients`. Mobile bottom tab bar: List, Recipes, Chat, Manage. Full route list: `docs/API.md`.

## Key Points

- Recipe dir = `recipe.yaml` (drives shopping list) + `recipe.md` (what people read) + optional image. Ingredient `food` names match `recipe_core/foods.yaml` (fuzzy fallback); omit `quantity` for unspecified.
- `web/instance/state.json`: selection, `last_used_date`, `_schedule_config`, `_week_plan`. Written atomically.
- Shopping list check-offs live in browser localStorage; server only tracks selected recipes.
- Single process by design (in-process scheduler and import threads). Keep `RECIPES_DEBUG=0` on the server.
- Service worker: own static files linked via `asset()` (`?v=mtime`); bump `CACHE_VERSION` when precache list/strategies change.

## Documentation Rule

`docs/` describes the current design. When a change alters behavior, data formats, routes, caching, or deployment, update the matching doc in the same commit.

## Known Issues

- Broken recipes: moraccan_chickpea_and_apricot_tagine, gnocchi_bake, firehouse_mac_n_cheese
- See `working/TODO.md`
