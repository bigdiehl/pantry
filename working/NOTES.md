# Working Notes

Last review: 2026-10-10. Consolidates the former `OPTIONAL_ENV_VARS.md` and `PWA_AND_IMPORTER_REVIEW.md`.

## Current State

| Area | Status |
|------|--------|
| PWA | Fixed (see findings). Untested on a phone. Needs HTTPS to install |
| Service install | `scripts/install_service.sh`, `setup_tailscale.sh`, `uninstall_service.sh`. Not yet run |
| Remote access | Tailscale recommended (`tailscale serve` provides HTTPS). Not set up |
| Recipe data | Moved to separate repo `../diehl_recipes` (history preserved) |
| Shopping list | Interactive list on `/`. Checkboxes persist in localStorage. Email/PDF/schedule UI only on `/archive/shopping_list` |
| Import | Gemini extract, validate, retry with feedback (max 3). Background job + progress UI. Untested on real URLs |
| Editor | YAML + markdown editing, image upload, promote/demote/archive |

## 2026-10-10 Review Findings

**PWA was not actually working.** Earlier notes called it "complete and verified". It was not:
- Service worker registered at `/static/service-worker.js`. Scope was `/static/`, so it controlled no pages and nothing worked offline. Now served at `/service-worker.js`.
- jQuery (`code.jquery.com`, no `crossorigin`) returns opaque responses, which were never cached. Recipes page would break offline. Opaque responses now cached; CDN libs precached.
- Cache-first on `/static/` with a fixed cache name meant CSS/JS updates never reached installed clients. Now stale-while-revalidate.
- `request.headers.get('accept').includes()` could throw on a null header.
- Network-first had no timeout. Now falls back to cache after 4s.
- Only recipes already viewed were readable offline. `/recipes_list` now prefetches all saved recipes.
- Manifest used `"any maskable"` on every icon, no `id`/`scope`. Fixed.
- `doc/PWA.md` claimed Tailscale works without HTTPS. Wrong: service workers require a secure context (localhost excepted). Plain `http://<lan-ip>:5000` cannot install or run offline.
- Lighthouse (2026-08-10, `http://192.168.1.139:5000`): perf 0.96, a11y 0.90, best-practices 0.74, SEO 0.90. Failures: no HTTPS, console errors, color contrast, heading order, missing meta description.

**Security:** `app.run(debug=True)` on `0.0.0.0` exposed the Werkzeug debugger (remote code execution) to the LAN. Now controlled by `RECIPES_DEBUG`; installer sets 0.

**Data repo split:** `data/` moved to `~/projects/diehl_recipes` and purged from local history of this repo. Backup of pre-rewrite repo: `~/projects/recipes_backup_20261010.tar.gz`. GitHub (`origin`) still has the old history until force-pushed.

**Data cleanup needed (in diehl_recipes):**
- `recipes/saved/saved/dinner/honey_lime_enchiladas/` is a stray nested dir; original location shows deleted. Probably meant for `archived/`.
- Empty `recipes/in_progress/` left over from the rename to `pending/`.

## Environment Variables

All optional. Missing vars disable features; protected routes return 503 with a message.

| Var | Enables / default |
|-----|-------------------|
| `GMAIL_SENDER`, `GMAIL_APP_PASSWORD` | Email, weekly schedule |
| `GEMINI_API_KEY` | Recipe import |
| `FLASK_SECRET_KEY` | Session key. Default is a dev value |
| `RECIPES_DATA_DIR` | Data repo path. Default `../diehl_recipes` |
| `RECIPES_HOST` / `RECIPES_PORT` | `0.0.0.0` / `5000` |
| `RECIPES_DEBUG` | `1` (dev). Service uses `0` |

`GET /api/features` reports `email_enabled` / `import_enabled`. Scheduler still runs with email disabled; it logs and returns.

## Importer Design

- Validates: name, servings (int), meal (BREAKFAST/LUNCH/DINNER), category (ENTREE/SALAD/DESSERT/SIDE), ingredients with `food`, markdown has `## Ingredients` and `## Instructions`, quantity sanity.
- Errors fed back to Gemini, up to `MAX_RETRIES` (3). Best-effort partial result returned with errors flagged in preview.
- `/import/extract` returns `job_id`; `/import/status/<job_id>` is polled.
- Possible: validate food names against `foods.yaml`, min ingredient/step counts.

## Design Decisions

- **Slugs:** snake_case directory names, Title Case for display.
- **Food names:** must match `foods.yaml`; unknown foods become `FoodType.Other` with a warning.
- **Quantities:** Pint format, or empty/`-` for unspecified. Dimensionless allowed ("2" chicken breasts).
- **State:** `web/instance/state.json` tracks selection and usage. APScheduler is in-memory (job rebuilt from config at startup).
- **Server:** Werkzeug dev server, single process. Fine for personal use; gunicorn would need the scheduler moved out of `__main__`.

## Open Questions

- Enable/disable + `min_period_weeks`: keep in `recipe.yaml` or move to `state.json`?
- Keep meal/category, or a freeform "section" field? Multiple meals per recipe?
- Store layout for shopping list ordering?
- Should the app commit/pull the data repo itself (editor saves, imports)?
