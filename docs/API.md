# API

JSON unless noted. Routes that need a missing API key return 503 with `{error}`.

## Pages (HTML)

`/` list, `/recipes_list` recipes (`?recipe=<slug>&status=&edit=1`), `/chat`, `/manage`, `/plan`,
`/import`, `/ingredients`. `/editor` redirects to `/recipes_list`. `/service-worker.js` is served from the root for scope.

## Recipes and selection

| Route | Does |
|-------|------|
| `POST /recipes_list/toggle/<slug>` | Toggle selection -> `{success, selected}` |
| `POST /deselect/<slug>` | Deselect |
| `GET /markdown/recipe/<name>` | `{filename, content}` rendered HTML; `name` is the recipe name (markdown title) |
| `GET /recipes/<slug>/<file>` | File from a saved recipe (also `/pending/<slug>/<file>`, `/archived/<slug>/<file>`) |
| `GET /api/features` | `{email_enabled, import_enabled}` |

## Shopping list (legacy, still routed)

| Route | Does |
|-------|------|
| `GET /markdown/shopping_list?show_sources=` | List as HTML |
| `GET/POST /download_shopping_list_pdf` | Printable PDF (inline): numbered recipes + Item/Quantity/Recipe tables. POST form field `state` = `{dismissed, custom}` from the list page |
| `POST /send_list` | Email the PDF |

## Editor

| Route | Does |
|-------|------|
| `GET /editor/recipes` | `{saved, pending, archived}` lists of `{slug, name, category, meal, status}` |
| `GET /editor/foods` | Known food names (autocomplete) |
| `GET /editor/recipe/<status>/<slug>` | `metadata`, `ingredients_md`, `instructions_md`, `image_url`, `image_width`, `preview_html`, `yaml_error`, `markdown_matched` |
| `POST /editor/recipe/<status>/<slug>` | Save form state -> writes `recipe.yaml` + `recipe.md`, returns `preview_html` |
| `POST/DELETE /editor/recipe/<status>/<slug>/image` | Upload (multipart `image`) or remove the photo |
| `POST /editor/recipe/<status>/<slug>/image/width` | `{width}` 100-1200 |
| `POST /editor/preview` | `{markdown, slug?}` -> `{html}` (no longer used by the UI) |
| `POST /pending/promote/<slug>`, `/editor/demote/<slug>` | pending <-> saved |
| `POST /editor/archive/<slug>`, `/editor/unarchive/<slug>` | to/from archived |
| `POST /editor/delete/<slug>`, `/pending/discard/<slug>`, `/editor/delete_archived/<slug>` | Delete |

## Import

| Route | Does |
|-------|------|
| `POST /import/extract` | JSON `{url}` or `{text}`, or multipart `images[]` + `text` note -> `{job_id, max_attempts}` |
| `GET /import/status/<job_id>` | `{status: running/done/error, events, result?, error?}`; `result.draft` is the recipe form state |
| `POST /import/confirm` | `{draft, destination: saved/pending}` -> `{slug, status}`; 409 if the name is taken. Without `draft`, saves the last extraction to pending |
| `POST /recipe/revise` | `{draft, instruction, history?}` -> `{draft, note}` (AI edit, nothing saved) |

## Chat

`POST /chat/message` `{messages: [{role: user/assistant, text}], search?: str}` ->
`{reply, reply_html, recipes: [{slug, name, reason, selected, image_url}], offer_search,
offer_query, web_query, web_recipes: [{title, url, site, image, summary, total_time}]}`.
With `search`, the model turn is skipped and the web search runs directly.

`/import?url=<url>` opens the import page in Link mode and starts extracting.

## Weekly plan

| Route | Does |
|-------|------|
| `GET /schedule/config` | `{config, next_run, last_plan, email_enabled, devices}` |
| `POST /schedule/config` | Save (validated/clamped) and reschedule -> `{config, next_run}` |
| `POST /schedule/send_now` | Run the plan now -> `{slugs, names, notified, emailed}` or `{skipped}` |

## Push

| Route | Does |
|-------|------|
| `GET /push/key` | `{public_key}` (base64url VAPID) |
| `POST /push/subscribe` | `{subscription, label}` |
| `POST /push/unsubscribe` | `{endpoint}` |
| `POST /push/status` | `{endpoint}` -> `{subscribed, devices}` |
| `POST /push/test` | Send a test to all devices -> `{sent}` |

## Ingredients

`GET /ingredients/list`, `POST /ingredients` (create), `POST /ingredients/<name>`
(update), `POST /ingredients/delete/<name>`.
