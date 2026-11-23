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
progress events (`fetch_fallback`, `attempt_start`, `validation_failed`, `retry`, `success`,
`giving_up`, `failed`) into `IMPORT_JOBS`. The page polls `/import/status/<id>`.

The finished result includes a `draft`: the recipe form state (markdown split into
`ingredients_md`/`instructions_md`, the page photo URL if any, `source`). The review step
edits it in the shared recipe form. `POST /import/confirm {draft, destination}` validates
it with the same rules as the editor (`_validate_recipe_form`), picks the slug from the
name (409 if taken), writes via `_write_recipe` into `saved/<breakfast|sides|dinner>/` or
`pending/`, downloads the photo, and writes `source.txt`.

YAML is always written with `yaml.safe_dump` of JSON-mode data. An earlier
`model_dump(mode="python")` wrote `!!python/object` enum tags that `safe_load` rejects,
which made every imported recipe open with defaults.

## AI recipe revision (`recipe_core/recipe_revise.py`)

`POST /recipe/revise {draft, instruction, history}` -> `{draft, note}`. Used by the
"Ask AI to change it" box in the editor and import review.

- Sends the editable fields as JSON plus the instruction; `response_schema=Revision`
  (`recipe: RecipeDraft`, `note`). Temperature 0.3.
- Prompt: change only what was asked plus what must change for consistency (scaling,
  substitutions touch both ingredient lists and the steps); keep shopping items and
  `ingredients_md` in agreement; a question gets an answer in `note` and no changes.
- `history` (last 10 instruction/note pairs) gives follow-ups context.
- Fields it doesn't edit (`enabled`, `min_period_weeks`, `image_url`, `source`) are
  carried over from the input. Nothing is saved; the client applies it, with undo.

## Models and quota (`recipe_core/gemini.py`)

Every Gemini call goes through `generate()`: primary model (`GEMINI_MODEL`, default
`gemini-2.5-flash`), then fallbacks (`GEMINI_FALLBACK_MODELS`, default
`gemini-3.5-flash-lite`) on 429 (quota) or 503 (overloaded). Each model has its own
free-tier quota; the free tier allows about 20 requests/day per model, which a few chat
turns plus an import can use up. `friendly_error()` turns failures into a short message
(daily limit, busy, or unavailable). The importer stops retrying on these errors instead
of burning more quota. Enabling billing on the key removes the daily cap.

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
ChatReply(reply: str,                       # short markdown, recipe names in bold
          recipes: [RecipePick(slug, reason,
                               missing,           # what they lack, when they listed what they have
                               key_ingredients)], # 3-6 primary ingredients otherwise
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
site, time, a 2-line summary, main ingredients (from `recipeIngredient`, amounts and
staples stripped), and **Import** -> `/import?url=...`, which starts the
import immediately.

### State

The conversation lives in the browser (`sessionStorage`) and is resent each turn.
The server keeps nothing. Error messages shown in the UI are not sent back to the model.

## Testing

Unit tests mock the Gemini client (`FakeModels`) or patch `extract_recipe` /
`recipe_chat` in the app module. Live checks are manual: run the app with `.env`
loaded and use the pages, or `curl` the endpoints.
