# Architecture

Single-process Flask app serving server-rendered pages plus a few JSON endpoints.
Recipe data lives on disk in a separate git repo. Runs on a home server (frank)
behind Tailscale; the phone uses it as an installed PWA.

## Components

```
Phone / browser (PWA)
  | HTTPS via `tailscale serve`         push notifications via browser push service
  v                                                   ^
Flask app (web/app.py, port 5000) ---------------------+  (pywebpush, VAPID)
  |-- recipe_core/       domain logic (no Flask)
  |-- APScheduler        weekly plan job (in-process)
  |-- import threads     Gemini extraction jobs
  |-- Gemini API         import + chat
  |-- Gmail SMTP         optional shopping list email
  v
Disk
  ../diehl_recipes/recipes/{saved,pending,archived}/   recipe files (git repo)
  web/instance/state.json                              selection, usage, settings
  web/instance/vapid.json, push_subscriptions.json     push keys + devices
  recipe_core/foods.yaml                               food registry
```

## Modules

| Module | Role |
|--------|------|
| `web/app.py` | Routes, recipe store (filesystem + state), weekly plan, scheduler setup |
| `recipe_core/recipe_lib.py` | Pydantic models (`RecipeData`, `Food`), Pint registry, `MergedIngredient` |
| `recipe_core/shopping_list.py` | Load recipes, merge ingredients, render list markdown |
| `recipe_core/foods.py` | Food registry: exact/fuzzy lookup, CRUD on `foods.yaml` (ruamel, keeps comments) |
| `recipe_core/gemini_importer.py` | URL/text/photo to `recipe.yaml` + `recipe.md`, validate, retry |
| `recipe_core/recipe_chat.py` | Chat turn: catalog prompt, structured JSON reply |
| `recipe_core/push.py` | VAPID keys, subscription store, `send_all` |
| `recipe_core/mailer.py` | SMTP message building and sending |

`recipe_core` never imports Flask. Keep it that way so it stays testable on its own.

## Request flow (shopping list page)

1. `GET /` calls `get_all_recipes()`: walks `saved/`, reads category/meal from each
   `recipe.yaml`, overlays `selected` from `state.json`.
2. `get_shopping_list_items()` merges ingredients of selected recipes
   (`get_merged_shopping_list`) into `main` and `secondary` (likely to have) groups.
3. The page embeds that JSON. All check-off/remove/add-item state stays in the
   browser's `localStorage`; the server only knows which recipes are selected.

Parsed recipe data is cached in `_shopping_list_cache` and invalidated on selection
changes, editor saves, and plan runs. Restart the app after editing recipe files by hand.

## Background work

| What | How | Notes |
|------|-----|-------|
| Weekly plan | APScheduler `BackgroundScheduler`, cron trigger rebuilt from config | Job is registered at startup (`__main__`) and on settings save |
| Import jobs | `threading.Thread` per job, progress in `IMPORT_JOBS` (in-memory, 1h TTL) | UI polls `/import/status/<id>` |

Both live in the web process. This is why the app runs as a single process with the
Werkzeug server: a multi-worker server (gunicorn) would run the scheduler once per
worker and lose in-memory import jobs between workers.

## State and writes

- `state.json` is written atomically (temp file + `os.replace`). Older non-atomic
  writes plus Flask's debug reloader (two processes) once corrupted it.
- No locking between concurrent requests beyond that; fine for one household.
- Recipe edits write straight into the data repo working tree. A weekly job on the
  server commits and pushes them ([DEPLOYMENT.md](DEPLOYMENT.md#data-backup-scriptsbackup_datash)).

## Configuration

`web/config.yaml` holds paths (relative to `web/`). Env vars override and toggle
features; see [DEPLOYMENT.md](DEPLOYMENT.md#environment). Features that need a missing
key are disabled and their routes return 503.

## Tests

`tests/` (pytest). `conftest.py` copies `recipe_core/test/` fixtures into a temp data
dir, sets `RECIPES_DATA_DIR` before importing the app, and redirects `STATE_FILE`,
`OUTPUT_DIR`, and `PUSH` to `tmp_path`. External services (Gemini, push, SMTP) are
always mocked. CI runs `uv run pytest` on every push and PR; frank runs it before deploying.
