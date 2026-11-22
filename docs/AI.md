# AI Features (Gemini)

All features use `gemini-2.5-flash` through `google-genai` and need `GEMINI_API_KEY`.
Without it, `IMPORT_ENABLED` is false and both routes return 503.

## Recipe import (`recipe_core/gemini_importer.py`)

### Inputs

| Mode | Content sent to Gemini |
|------|------------------------|
| URL | Page fetched with `requests`, main content extracted (BeautifulSoup), first 10k chars. If the site refuses the fetch, Gemini's URL context tool reads the page instead (slower; progress shows `fetch_fallback`) |
| Text | Pasted text |
| Photo | 1-6 images as inline parts, plus an optional note; `PHOTO_INSTRUCTIONS` asks for a faithful transcription and no image tag |

Photos are downscaled in the browser (longest edge 2000px, JPEG 0.85) before upload.
The server checks type (`image/*`), count (6), and size (15 MB each).

### Output contract

Gemini returns plain text with two sections, `---YAML---` (the `recipe.yaml` fields)
and `---MARKDOWN---` (the `recipe.md` body). Plain text rather than JSON mode because
the markdown body is long and multi-line.

### Validate and retry

```
attempt 1..MAX_RETRIES (3):
  call Gemini (with feedback from the last attempt, if any)
  missing section markers / YAML parse error / validation errors -> feedback, retry
  valid -> ImportResult
last attempt still invalid -> return best effort with validation_errors flagged
```

Validation: required fields and types, enum values, ingredients have `food`, markdown
has `## Ingredients` and `## Instructions`, quantities parse.

### Job flow

`POST /import/extract` starts a thread and returns `job_id`. The thread reports
progress events (`attempt_start`, `validation_failed`, `retry`, `success`,
`giving_up`, `failed`) into `IMPORT_JOBS`. The page polls `/import/status/<id>`;
the finished result is stored in the Flask session so `POST /import/confirm` can
save it to `pending/` (with `source.txt`). The UI then opens the editor on it.

## Recipe chat (`recipe_core/recipe_chat.py`)

Two steps: answer from saved recipes (one fast model call), then, if the user wants,
search the web for new ones.

### Prompt

System instruction = rules + a catalog of saved recipes, one line each:

```
slug | name | category, meal | last made 2026-09-13 | on list | ingredient, ingredient, ...
```

Conversation is sent as alternating `user`/`model` contents (last 20 messages, each
capped at 4000 chars). Assistant turns are resent with the cards they showed appended
(`[Saved recipes shown: ...]`, `[Web recipes shown: ...]`) so follow-ups like
"more like the second one" have context.

### Structured reply

`response_schema=ChatReply`, JSON mode:

```python
ChatReply(reply: str,                       # short markdown
          recipes: [RecipePick(slug, reason)],
          offer_search: bool,               # show "Look for new recipes"
          offer_query: str | None,          # query to run if accepted
          web_search: str | None)           # run a web search now
```

The route drops any slug not in the catalog (no hallucinated recipes), attaches the
`selected` flag and a thumbnail (`image.*`, else any image in the recipe folder), and
renders `reply` to HTML after escaping it.

When to search: the model sets `web_search` when the user accepts the offer ("yes"),
says "look for more", or asks for "recipes like X". The "Look for new recipes" button
skips that model turn: it posts `search: offer_query` and the route searches directly.

### Web recipe search (`recipe_core/recipe_search.py`)

```
Gemini + google_search tool  ->  ~8 grounding URLs (Google redirect links)   ~7s
resolve each redirect (no download), fetch target, 3s timeout, in parallel   ~2s
  200 + schema.org Recipe JSON-LD -> full card: name, photo, total time, summary
  401/403/429/503 (bot protection) -> basic card: title from URL slug, no photo
  anything else, or roundup titles ("...Recipes", "Best ...") -> dropped
photo cards first, de-duplicated, max 4
```

We do not work around bot protection (no browser impersonation). Reading pages with
Gemini's URL context tool works on blocked sites but took ~45s for four pages, too slow
for chat; the importer uses it as a fallback instead (see above).

Cards show the photo (hotlinked, `referrerpolicy="no-referrer"`, hidden if it fails),
site, time, a 2-line summary, and **Import** -> `/import?url=...`, which starts the
import immediately.

### State

The conversation lives in the browser (`sessionStorage`) and is resent each turn.
The server keeps nothing. Error messages shown in the UI are not sent back to the model.

## Testing

Unit tests mock the Gemini client (`FakeModels`) or patch `extract_recipe` /
`recipe_chat` in the app module. Live checks are manual: run the app with `.env`
loaded and use the pages, or `curl` the endpoints.
