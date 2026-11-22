# Project TODOs

## Ideas to decide (not started)

- [ ] **Bring back "pending" on the Recipes page?** The redesign removed the Pending tab
      from Recipes; pending recipes are only visible in Manage > Edit recipes. Decide
      whether Recipes should show them (read-only, or with an Approve button) or whether
      Manage is the right home.

## High Priority

### Server (frank) / Phone
- [x] App installed on phone via Tailscale HTTPS (2026-11-22)
- [ ] Turn on notifications on the phone (Manage > Weekly plan), send a test
- [ ] Verify offline on the phone: list, recipes, photos
- [ ] Remove old `~/samba_share/recipes_app` and `/etc/recipes_app.env` on frank
- [ ] Delete `~/projects/recipes_prefilter_20261122.bundle` and `~/projects/recipes_git_backup_20261122`
- [ ] Add `sdiehl` to `systemd-journal` on frank (read deploy logs without sudo)

### Shopping List
- [ ] Offline recipe selection changes (queue + sync)
- [ ] Mobile usability testing in a store

### Recipe Import
- [ ] Test on real URLs and real cookbook photos, including the retry path
- [ ] Import meal type: desserts get filed as DINNER (only BREAKFAST/LUNCH/DINNER exist)

## Medium Priority

### Recipe Management
- [ ] Validate both recipe.yaml and recipe.md exist on load
- [ ] Fix broken recipes:
  - moraccan_chickpea_and_apricot_tagine
  - gnocchi_bake (missing quantities)
  - firehouse_mac_n_cheese (missing quantities)
- [ ] Pending recipes with null servings/meal/category fail to load (log warnings)
- [ ] Recipes with an image tag but no image file show a broken image (e.g. butternut squash soup)

### Weekly Plan
- [ ] Mark recipes as cooked (set `last_used_date` when made, not when picked)
- [ ] Catch up a missed run if the server was down at the scheduled time
- [ ] Refine selection (N entrees + M sides)

### Shopping List Features
- [ ] Scale quantities by number of people
- [ ] Custom unit rules (e.g., x tbsp butter = 1 stick)
- [ ] Spice blend lookup (expand to individual spices)
- [ ] Better handling of mixed quantity types (1 bunch + unspecified)

## Low Priority

- [ ] Support multiple meals per recipe (lunch + dinner)
- [ ] Print recipe functionality
- [ ] Recipe photos for missing images
- [ ] Lighthouse pass (contrast, heading order)

## Completed

- [x] WYSIWYG recipe editor, import review with edit/AI changes, Add to recipes (2026-11-22)
- [x] Fixed: imported recipe.yaml unreadable (python tags); mixed-number quantities parsed wrong (2026-11-22)
- [x] UI redesign: tab navigation, list/recipe/editor views, blue theme, offline fonts (2026-11-22)
- [x] Recipe chat with voice input; photo import (2026-11-22)
- [x] Weekly plan page with push notifications; weekly data backup job (2026-11-22)
- [x] Offline: recipe photos warmed, versioned assets (2026-11-22)
- [x] Docs moved to `docs/` as developer design docs (2026-11-22)
- [x] frank on pantry.service + Tailscale HTTPS; frank_web_server retired (2026-11-22)
- [x] Purged recipe data from history, consolidated on master, renamed repo to pantry (2026-11-22)
- [x] diehl_recipes pushed to GitHub (2026-11-22)
- [x] pytest suite, GitHub Actions CI, auto-deploy timer (2026-11-22)
- [x] PWA manifest, service worker, icons (2026-10-10)
- [x] Recipe data split to diehl_recipes repo (2026-10-10)
- [x] Recipe editor, Gemini import with validation, ingredient editor
- [x] Recipe selection tracking
