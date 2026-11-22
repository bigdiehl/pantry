# Architecture

## Stack

- Python 3.11+ / Flask
- pint (units), pydantic (validation), google-genai (import), weasyprint (PDF)
- APScheduler for weekly emails
- Deployed via systemd (`scripts/install_service.sh`) on port 5000

## Structure

```
recipe_core/         Core logic (models, shopping list, foods, units, importer)
web/                 Flask app, routes, templates, static files
../diehl_recipes/    Separate data repo (RECIPES_DATA_DIR)
recipes/
  ├── saved/         Active recipes
  ├── pending/       Imported, awaiting approval
  └── archived/      Retired recipes, kept but out of rotation
```

## Data Storage

**Recipe directory:** `recipe.yaml` + `recipe.md` + `image.jpg` (optional)

**State file:** `web/instance/state.json` - tracks selection, last_used_date, weeks_since_last

## Shopping List Logic

1. Load selected recipes
2. Extract ingredients, group by food name
3. Merge compatible units, sum quantities
4. Separate "likely to have" items (spices, staples)
5. Sort by category (DAIRY, MEAT, VEGETABLE)

## PWA

- Service worker caches static assets and recipes
- Works offline for browsing/viewing
- Network required for import, email, schedule
