# AI Features (Gemini)

Both features use `gemini-2.5-flash` through `google-genai` and need `GEMINI_API_KEY`.
Without it, `IMPORT_ENABLED` is false and both routes return 503.

## Recipe import (`recipe_core/gemini_importer.py`)

### Inputs

| Mode | Content sent to Gemini |
|------|------------------------|
| URL | Page fetched with `requests`, main content extracted (readability + BeautifulSoup), first 10k chars |
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

### Prompt

System instruction = rules + a catalog of saved recipes, one line each:

```
slug | name | category, meal | last made 2026-09-13 | on list | ingredient, ingredient, ...
```

Conversation is sent as alternating `user`/`model` contents (last 20 messages, each
capped at 4000 chars). Must end with a user message.

### Structured reply

`response_schema=ChatReply`, JSON mode:

```python
ChatReply(reply: str,                      # short markdown
          recipes: [RecipePick(slug, reason)],
          ideas: [RecipeIdea(name, summary)])
```

The route drops any slug not in the catalog (no hallucinated recipes), attaches the
current `selected` flag, and renders `reply` to HTML after escaping it. The page shows
picks as cards with Add/On list buttons and ideas with a web search link.

### State

The conversation lives in the browser (`sessionStorage`) and is resent each turn.
The server keeps nothing. Error messages shown in the UI are not sent back to the model.

## Testing

Unit tests mock the Gemini client (`FakeModels`) or patch `extract_recipe` /
`recipe_chat` in the app module. Live checks are manual: run the app with `.env`
loaded and use the pages, or `curl` the endpoints.
