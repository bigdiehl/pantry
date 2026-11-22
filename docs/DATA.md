# Data

## Recipe files (diehl_recipes repo)

```
recipes/
  saved/       active recipes; nested folders allowed (breakfast/, dinner/, sides/)
  pending/     imported or demoted, awaiting review; flat
  archived/    out of rotation, kept for reference; flat
  spice_blends.md
```

Each recipe is a directory named by its **slug** (snake_case, unique across all three
states). The app finds recipes by walking for `recipe.yaml`.

| File | Purpose |
|------|---------|
| `recipe.yaml` | Structured data: drives the shopping list and selection |
| `recipe.md` | What people read: title, servings, image, ingredients, instructions |
| `image.*` | Optional photo, referenced from `recipe.md` |
| `source.txt` | Import source (URL, "pasted text", "photo (N images)") |

### recipe.yaml (`RecipeData`)

```yaml
name: Butternut Squash Soup
servings: 4
meal: dinner              # BREAKFAST | LUNCH | DINNER (case-insensitive)
category: entree          # ENTREE | SALAD | DESSERT | SIDE
min_period_weeks: 4       # weekly plan won't repeat it sooner
enabled: true             # eligible for weekly auto-pick
ingredients:
  - food: onion           # matched against foods.yaml
    quantity: 1 cup       # Pint string; omit for "unspecified"
```

`ingredients` here is the shopping list view (simple food names). The human-readable
ingredient list lives in `recipe.md` and can differ ("1 cup chopped onion").

### recipe.md

The editor regenerates the header (`# Name`, `Servings: N`, image tag) from the YAML
and image, and stores the body as two parts split on `## Ingredients` and the next
heading (usually `## Instructions`/`## Directions`). Image paths are relative; routes
rewrite them to `/recipes/<slug>/...` (or `/pending/`, `/archived/`) when rendering.

## state.json (`web/instance/`, not in git)

```json
{
  "<slug>": {"selected": true, "last_used_date": "2026-11-22"},
  "_schedule_config": {"enabled": true, "num_recipes": 3, "frequency_weeks": 1,
                       "day_of_week": 6, "send_time": "09:00", "fresh_start": true,
                       "notify": true, "send_email": false, "recipients": ""},
  "_week_plan": {"created": "2026-11-22T09:00:00", "slugs": [...], "names": [...]}
}
```

Keys starting with `_` are app settings, not recipes. Slugs that no longer exist on
disk are ignored. `day_of_week` uses APScheduler numbering (0 = Monday).

## Food registry (`recipe_core/foods.yaml`)

```yaml
- names: [white onion, onion]   # first name is the display name
  category: VEGETABLE           # BAKING DAIRY FRUIT MEAT OTHER SPICE VEGETABLE
  preferred_unit: cup           # optional: convert merged totals to this
  min_amount: 0.25              # optional: drop from list below this (in preferred_unit)
  likely_to_have: true          # optional: goes in "Probably have"
  preferred_vendor: Costco      # optional: store filter on the list
```

Lookup (`foods.get_food`): exact alias match, then fuzzy (`rapidfuzz`
token_sort_ratio >= 85), else a default `OTHER` food. It never raises, so a typo
in a recipe degrades to an uncategorized item instead of breaking the list.

## Quantities and merging

- Parsed with Pint (`parse_quantity`). `"3"` is dimensionless; unknown units
  (`"2 zorbles"`) are registered on the fly as their own base unit.
- Custom base units: `bundle`, `can(s)`, `tub(s)`, `bunch`, `clove(s)`, `slice(s)`, `na`.
- `MergedIngredient` keeps one `QuantityGroup` per incompatible unit family:
  `1 cup + 0.5 cup = 1 1/2 cup`, but `1 cup + 2 cans` stays as two parts.
- Ingredients without a quantity are tracked per recipe ("unspecified from [2]").
- Display uses fractions with denominators up to 8.

## Slugs and names

Slug = directory name. Display name on lists is `slug.title()`; `recipe.yaml` `name`
is used in chat, the editor, and rendered markdown. `/markdown/recipe/<name>` looks
up by the title-cased slug, not the YAML name.
