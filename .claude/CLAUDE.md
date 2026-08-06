# Recipe Management Application

Personal recipe management web app: browse recipes, generate shopping lists, schedule weekly emails, import recipes via Gemini AI.

## Quick Reference

**Stack:** Flask (Python 3.11+), Pint, Pydantic, Google GenAI, WeasyPrint, APScheduler

**Structure:**
- `recipe_core/` - Core logic (models, shopping list, foods, units, importer, mailer)
- `web/` - Flask app, templates, static files, routes
- `data/recipes/saved/` - Active recipes (breakfast/, dinner/, sides/)
- `data/recipes/pending/` - Imported recipes awaiting approval
- `doc/` - Permanent documentation
- `working/` - Project TODOs and notes

**Run:** `uv run web/app.py` (localhost:5000)

**Env vars:** GMAIL_SENDER, GMAIL_APP_PASSWORD, GEMINI_API_KEY

## Recipe Storage

Each recipe is a directory containing:
- `recipe.yaml` - Name, servings, ingredients, meal, category, enabled, min_period_weeks
- `recipe.md` - Instructions (markdown)
- `image.jpg` (optional)

**Ingredient format:**
```yaml
ingredients:
  - food: chicken breast  # Must match foods.py
    quantity: 2 lbs       # Pint format or "-" for unspecified
```

**State:** `web/instance/state.json` tracks selection, last_used_date, weeks_since_last

## Key Features

**Shopping List:** Merges ingredients from selected recipes, sums compatible units, groups by category (DAIRY, MEAT, VEGETABLE), separates "likely to have" items

**Scheduling:** APScheduler sends weekly shopping list PDF via email, auto-selects recipes based on min_period_weeks

**Import:** Gemini API extracts recipes from URLs/text → preview → save to pending/ → edit → promote to saved/

**PWA:** Service worker enables offline browsing, install to home screen

**Interactive List Demo:** /shopping_demo - checkboxes, add/remove items, offline support

## Web Routes

**Pages:** `/` (home), `/recipes_list` (browse), `/editor` (edit/import), `/shopping_demo`

**API:**
- Recipe selection: `POST /recipes_list/toggle/<slug>`, `POST /deselect/<slug>`
- Shopping list: `GET /markdown/shopping_list`, `POST /send_list`, `GET /download_shopping_list_pdf`
- Editor: `GET /editor/recipes`, `GET|POST /editor/recipe/<status>/<slug>`, `POST /editor/preview`
- Import: `POST /import/extract`, `POST /import/confirm`
- Schedule: `GET|POST /schedule/config`, `POST /schedule/send_now`

## Custom Units

Pint extended with: `bundle`, `can`, `tub`, `bunch`, `clove`, `slice`, `na` (not applicable)

Compatible units merge: "1 cup" + "0.5 cup" = "1.5 cup"

Incompatible units separate: "2 cans + 1 cup"

## Known Issues

**Broken recipes:** moraccan_chickpea_and_apricot_tagine, gnocchi_bake, firehouse_mac_n_cheese

**TODO (see working/TODO.md):**
- Test PWA on phone
- Setup remote access (Tailscale or Cloudflare Tunnel)
- Integrate interactive shopping list with real data
- Add import verification (validate + retry with Gemini feedback)

## Documentation

- `doc/ARCHITECTURE.md` - System design
- `doc/SETUP.md` - Installation and config
- `doc/API.md` - Route reference
- `doc/PWA.md` - Progressive web app details
- `doc/REMOTE_ACCESS.md` - VPN/tunnel options
- `doc/INTERACTIVE_SHOPPING_LIST.md` - Demo implementation
- `working/TODO.md` - Project tasks
- `working/NOTES.md` - Working notes
