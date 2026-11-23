# Frontend

Server-rendered Jinja templates with page-local JavaScript. No build step, no
framework. Bootstrap 5.0.2 for base styles and the dropdown/modal JS; everything
visual is in `web/static/css/style.css`.

## Pages

| Route | Template | Tab |
|-------|----------|-----|
| `/` | `index.html` | List |
| `/recipes_list` | `recipes_list.html` + `scripts/recipes_list.js` | Recipes (browse, read, edit) |
| `/chat` | `chat.html` | Chat |
| `/manage` | `manage.html` | Manage |
| `/plan`, `/import`, `/ingredients` | one template each | Manage |

`/editor` redirects to the Recipes page (`?recipe=&status=&edit=1`) so old links keep working.

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

**List + detail + edit** (Recipes): Saved / Pending / Archived tabs. Tapping a recipe opens
the detail: a full-screen sheet on mobile, a sticky panel beside the list on desktop
(>= 992px). The detail has two modes:
- view: rendered recipe; Add/On list for saved recipes; menu with Move, Archive/Restore, Delete.
- edit: the shared recipe form; Save / Cancel. The photo block is moved into the form's
  `.doc-photo-slot` (after Servings) and floats right at its set width (`--photo-w`) like the
  rendered recipe; full width on phones. No separate preview: the form already looks like
  the recipe, and Save returns to the rendered view.

Desktop: in view mode the detail is a sticky panel with its own scroll area, so the recipe
stays put while you scroll the list. In edit mode (`.recipe-detail.editing`) the panel grows
with its content and the page scrolls; the detail bar and formatting toolbars stick under
the site header.

History entries: mobile pushes `{sheet: 'view'}` then `{sheet: 'edit'}`, desktop only
`{sheet: 'edit'}`, so Back always undoes one step; leaving edit with unsaved changes asks
first. Saved recipes are viewed via `/markdown/recipe` (offline-warmed); pending and
archived via `/editor/recipe/<status>/<slug>`. Editing needs a connection.

**Import review**: after extraction the draft opens in the recipe form; Add to recipes
(saved/), Save for later (pending/), or Discard. A photo found on the page is shown and
downloaded on save unless unticked.

**Recipe form** (`_recipe_form.html` + `scripts/recipe_form.js`): one form used by Edit
recipes (Recipes page edit mode) and the import review. `RecipeForm.mount(el, {onChange})` returns `get()`/`set(state)`/`reset()`.
State is the recipe form JSON: `name, servings, servings_note, category, meal, enabled,
min_period_weeks, ingredients[{food, quantity}], ingredients_md, instructions_md`; unknown keys
(`image_url`, `source`) pass through untouched.

Layout mirrors the rendered recipe (`.recipe-doc.markdown-content`): the name as an
editable title, a fixed "Servings:" label with a number input and a free-text note, then
fixed "Ingredients" and "Instructions" headings, each over a rich text area. Headings and
the "Servings:" label are not editable. The form is two white cards (`.form-card`) with a
gap: the recipe (with the AI box on top), then "Shopping list and settings" (type, meal,
repeat weeks, auto-pick, shopping list items), always expanded. In edit mode the Recipes
detail panel turns to the page background so the cards stand apart. It contains:
- Two `RichEditor`s (`scripts/rich_editor.js`): contenteditable with a toolbar (section
  heading, bold, italic, bullets, numbers; shown only while that section has focus) and a
  "Text" toggle for raw markdown. `marked`
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
| `recipesLast`, `recipesGroupBy` | localStorage | Recipes | Last opened recipe (`{slug, status}`), grouping |
| `recipeChat` | sessionStorage | Chat | Conversation (cleared on New chat / tab close) |

List rows are keyed `"<Category>::<food name>"`; custom items by index. When the
server's `_week_plan.created` differs from the stored `week`, checks and dismissals
reset so each plan starts a clean checklist.

## Conventions

- `html, body` use `overflow-x: clip`, not `hidden`: `hidden` on both makes body a scroll
  container and breaks every `position: sticky` (header, toolbars). Inside the recipe
  detail's own scroll area, toolbars use `--sticky-top: 0`.
- Escape anything user- or model-provided before putting it in `innerHTML` (`esc()`
  helpers in each page). Chat replies are HTML-escaped server-side before markdown.
- Own static files are linked with `asset('path')`, which appends `?v=<mtime>`
  (see [PWA.md](PWA.md#asset-versioning)). Vendored files use `url_for('static', ...)`.
- jQuery is only used by the ingredients page; new code uses plain JS.
- Vendored libs: Bootstrap, jQuery, `marked`, `turndown`, fonts (`static/vendor/`).
