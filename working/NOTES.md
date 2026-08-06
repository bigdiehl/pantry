# Working Notes

## Current State

**PWA:** Basic implementation done. Manifest, service worker, icons all in place. Needs testing on actual phone.

**Remote Access:** Not yet configured. Need to pick between Tailscale (easiest, private) or Cloudflare Tunnel (public, requires domain). See doc/REMOTE_ACCESS.md.

**Interactive Shopping List:** Demo exists at /shopping_demo. Works with sample data. Not integrated with real shopping list yet. Needs API hookup and offline sync.

**Recipe Import:** Works but has no verification. Gemini sometimes makes mistakes - needs validation + retry loop.

## Known Issues

**Broken Recipes:**
- moraccan_chickpea_and_apricot_tagine - loading error
- gnocchi_bake - missing quantities on half the ingredients
- firehouse_mac_n_cheese - same issue

**Pending Recipes:**
- thai_mango_salad_mendocino_farms_dupe - in pending/, needs review

## Design Decisions

**Recipe slugs:** snake_case directory names, converted to Title Case for display

**Food names:** Must match foods.py entries for proper categorization. Unknown foods default to FoodType.Other with warning.

**Quantities:** Pint format ("2 cups", "1 tbsp") or empty/"-" for unspecified. Dimensionless allowed (e.g., "2" chicken breasts).

**State management:** state.json tracks selection + usage. APScheduler in-memory only (resets on restart).

## Next Steps

1. Test PWA on phone (install, offline mode)
2. Pick and setup remote access method
3. Implement import verification with Gemini feedback loop
4. Integrate demo shopping list with real data

## Questions

- Should enable/disabled + min_period_weeks stay in recipe.yaml or move to state.json?
- Keep meal/category or replace with freeform "section" field?
- Support multiple meals per recipe?
- Store layout for shopping list ordering?
