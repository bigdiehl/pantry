# API

## Pages

- `GET /` - Home (selected recipes + interactive shopping list table)
- `GET /recipes_list` - Browse/select recipes
- `GET /editor` - Edit or import recipes
- `GET /archive/shopping_list` - Archived: markdown-based shopping list page (email/PDF/schedule UI)
- `GET /archive/shopping_demo` - Archived: shopping list prototype using fake demo data

## Recipe Selection

- `POST /recipes_list/toggle/<slug>` - Toggle selection
- `POST /deselect/<slug>` - Deselect recipe

## Shopping List

- `GET /markdown/shopping_list` - Get list HTML
- `POST /send_list` - Email PDF (form: recipient_email)
- `GET /download_shopping_list_pdf` - Download PDF

## Editor

- `GET /editor/recipes` - List all recipes (saved, pending, and archived)
- `GET /editor/foods` - Sorted list of known food names, for ingredient autocomplete
- `GET /editor/recipe/<status>/<slug>` - Load for editing (structured metadata + split ingredients_md/instructions_md + preview_html)
- `POST /editor/recipe/<status>/<slug>` - Save (JSON: name, servings, category, meal, enabled, min_period_weeks, ingredients, ingredients_md, instructions_md) - writes recipe.yaml + recipe.md
- `POST /editor/recipe/<status>/<slug>/image` - Add/replace the recipe's image (multipart: image)
- `POST /editor/recipe/<status>/<slug>/image/width` - Adjust the recipe's image display width (JSON: width, 100-1200)
- `DELETE /editor/recipe/<status>/<slug>/image` - Remove the recipe's image
- `POST /editor/preview` - Render markdown (legacy helper, no longer used by the editor UI)
- `POST /editor/demote/<slug>` - Move to pending
- `POST /editor/delete/<slug>` - Delete recipe
- `POST /editor/archive/<slug>` - Move (from saved or pending) to archive
- `POST /editor/unarchive/<slug>` - Restore an archived recipe to saved
- `POST /editor/delete_archived/<slug>` - Delete an archived recipe

## Import

Extraction runs in a background thread and retries against validation errors (up to `MAX_RETRIES`, feeding each failure back to Gemini), so the web UI polls for progress instead of blocking on one long request.

- `POST /import/extract` - Start a background extraction job (JSON: url or text). Returns `{job_id, max_attempts}`
- `GET /import/status/<job_id>` - Poll a job: `{status: running|done|error, events: [...], max_attempts}`, plus `result` (recipe, markdown_preview, slug, source, validation_errors) when done, or `error` when errored
- `POST /import/confirm` - Save the extracted recipe (from the last-polled job) to pending/

## Schedule

- `GET /schedule/config` - Get config + next send date
- `POST /schedule/config` - Update (JSON: day, hour, minute, recipe_count, recipients)
- `POST /schedule/send_now` - Trigger manual send

## Static

- `GET /recipes/<slug>/<file>` - Serve recipe files
- `GET /pending/<slug>/<file>` - Serve pending files
- `GET /archived/<slug>/<file>` - Serve archived files
- `GET /markdown/recipe/<name>` - Recipe markdown HTML
