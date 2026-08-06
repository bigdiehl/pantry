# API

## Pages

- `GET /` - Home (selected recipes + shopping list)
- `GET /recipes_list` - Browse/select recipes
- `GET /editor` - Edit or import recipes
- `GET /shopping_demo` - Interactive shopping list demo

## Recipe Selection

- `POST /recipes_list/toggle/<slug>` - Toggle selection
- `POST /deselect/<slug>` - Deselect recipe

## Shopping List

- `GET /markdown/shopping_list` - Get list HTML
- `POST /send_list` - Email PDF (form: recipient_email)
- `GET /download_shopping_list_pdf` - Download PDF

## Editor

- `GET /editor/recipes` - List all recipes
- `GET /editor/recipe/<status>/<slug>` - Load for editing
- `POST /editor/recipe/<status>/<slug>` - Save (JSON: yaml, markdown)
- `POST /editor/preview` - Render markdown
- `POST /editor/demote/<slug>` - Move to pending
- `POST /editor/delete/<slug>` - Delete recipe

## Import

- `POST /import/extract` - Extract via Gemini (form: source_type, source)
- `POST /import/confirm` - Save to pending/

## Schedule

- `GET /schedule/config` - Get config + next send date
- `POST /schedule/config` - Update (JSON: day, hour, minute, recipe_count, recipients)
- `POST /schedule/send_now` - Trigger manual send

## Static

- `GET /recipes/<slug>/<file>` - Serve recipe files
- `GET /pending/<slug>/<file>` - Serve pending files
- `GET /markdown/recipe/<name>` - Recipe markdown HTML
