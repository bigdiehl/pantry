# Frontend

Server-rendered Jinja templates with page-local JavaScript. No build step, no
framework. Bootstrap 5.0.2 for base styles and the dropdown/modal JS; everything
visual is in `web/static/css/style.css`.

## Pages

| Route | Template | Tab |
|-------|----------|-----|
| `/` | `index.html` | List |
| `/recipes_list` | `recipes_list.html` + `scripts/recipes_list.js` | Recipes |
| `/chat` | `chat.html` | Chat |
| `/manage` | `manage.html` | Manage |
| `/plan`, `/editor`, `/import`, `/ingredients` | one template each | Manage |

`archive_shopping_list.html` and `archive_shopping_demo.html` are kept for reference
only; their routes were removed.

## Shell and navigation (`base.html`)

- `active_page` (passed by each route) maps to one of four sections; that drives the
  highlighted tab.
- Mobile (< 768px): fixed bottom tab bar. Desktop: links in the top header.
- Manage subpages have no sub-navigation; browser back returns to Manage.
- Blocks: `title`, `head`, `content`, `scripts`. Page scripts go in `scripts` so they
  run after Bootstrap loads.

## View patterns

**List + detail** (Recipes): one grid. Mobile shows the list; tapping opens the detail
as a full-screen sheet and pushes a history entry so the back button closes it.
Desktop (>= 992px) shows the list and a sticky detail panel side by side.

**List -> edit -> preview** (Edit recipes): `#editorLayout[data-view]` is `list`,
`edit`, or `preview`. Mobile shows one view at a time, and each step forward is a
`history.pushState`; `popstate` restores the view (and asks before discarding unsaved
edits). Desktop keeps the list visible and swaps edit/preview beside it.
Preview always reflects saved content (Preview saves first when dirty), because the
server builds the final markdown from YAML + image + body.

**Import review**: after extraction the draft opens in the recipe form; Add to recipes
(saved/), Save for later (pending/), or Discard. A photo found on the page is shown and
downloaded on save unless unticked.

**Recipe form** (`_recipe_form.html` + `scripts/recipe_form.js`): one form used by Edit
recipes and the import review. `RecipeForm.mount(el, {onChange})` returns `get()`/`set(state)`/`reset()`.
State is the recipe form JSON: `name, servings, category, meal, enabled, min_period_weeks,
ingredients[{food, quantity}], ingredients_md, instructions_md`; unknown keys (`image_url`,
`source`) pass through untouched. It contains:
- Two `RichEditor`s (`scripts/rich_editor.js`): contenteditable with a toolbar (section
  heading, bold, italic, bullets, numbers) and a "Text" toggle for raw markdown. `marked`
  renders markdown in, `turndown` converts back; paste is plain text only. Storage stays
  markdown. Uses `document.execCommand`, which is deprecated but supported everywhere and
  needs no build step.
- Shopping list item rows (food + quantity, foods datalist from `/editor/foods`).
- "Ask AI to change it": posts the current state to `/recipe/revise`, applies the result,
  shows the model's note, and keeps an undo stack plus the instruction history.

**Settings rows** (Weekly plan): `.panel.settings > .setting`, switches and steppers,
autosaved on change (debounced 400ms).

## Styling

- Tokens in `:root`: `--accent` (#1e88e5), `--accent-dark`, `--accent-soft`, `--text`
  (#2c3e50), `--muted`, `--bg`, `--surface`, `--border`, `--radius`, `--header-h`,
  `--tabbar-h`, `--safe-bottom`. Use them instead of literal colors.
- Fonts: Lato (body), Playfair Display (brand, page titles, recipe headings). Vendored
  in `static/vendor/fonts/` so they work offline.
- `.markdown-content` keeps the original recipe styling (Playfair headings with blue
  underlines). On phones, recipe images ignore their float/width and go full width.
- Shared components: `.page`, `.page-header`, `.panel`, `.section-label`, `.pill-btn`
  (`.on` = selected), `.segmented`, `.icon-btn`, `.chip`, `.empty-note`.
- No emoji or pictographic characters; icons are inline SVG.

## Client state

| Key | Storage | Page | Holds |
|-----|---------|------|-------|
| `shopping_list_table_state` | localStorage | List | `{checked, dismissed, custom, week}` |
| `cartOpen`, `haveOpen` | sessionStorage | List | Collapsible sections open |
| `recipesLast`, `recipesGroupBy` | localStorage | Recipes | Last opened recipe, grouping |
| `lastSelectedRecipe/Status`, `editorGroupBy` | localStorage | Editor | Same for the editor |
| `recipeChat` | sessionStorage | Chat | Conversation (cleared on New chat / tab close) |

List rows are keyed `"<Category>::<food name>"`; custom items by index. When the
server's `_week_plan.created` differs from the stored `week`, checks and dismissals
reset so each plan starts a clean checklist.

## Conventions

- `html, body` use `overflow-x: clip`, not `hidden`: `hidden` on both makes body a scroll
  container and breaks every `position: sticky` (header, editor bars, toolbars).
- Escape anything user- or model-provided before putting it in `innerHTML` (`esc()`
  helpers in each page). Chat replies are HTML-escaped server-side before markdown.
- Own static files are linked with `asset('path')`, which appends `?v=<mtime>`
  (see [PWA.md](PWA.md#asset-versioning)). Vendored files use `url_for('static', ...)`.
- jQuery is only used by the editor and ingredients pages; new code uses plain JS.
- Vendored libs: Bootstrap, jQuery, `marked`, `turndown`, fonts (`static/vendor/`).
