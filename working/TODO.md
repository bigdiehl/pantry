# Project TODOs

## High Priority

### PWA on Phone
- [ ] Run `scripts/install_service.sh` on server
- [ ] Enable MagicDNS + HTTPS certs in Tailscale admin, run `scripts/setup_tailscale.sh`
- [ ] Install from `https://<host>.<tailnet>.ts.net` on Android/iOS
- [ ] Verify offline: shopping list, recipe list, recipe content, images
- [ ] Fix Lighthouse items: color contrast, heading order, meta description

### Repo Split / Git
- [ ] Create `bigdiehl/diehl_recipes` on GitHub, push `~/projects/diehl_recipes`
- [ ] Force-push rewritten `dev` and `master` here (purges data/ from GitHub)
- [ ] Re-clone any other checkouts of this repo (old history)
- [ ] Delete `~/projects/recipes_backup_20261010.tar.gz` once confirmed
- [ ] Clean up data repo: stray `recipes/saved/saved/`, empty `in_progress/`
- [ ] Delete or gitignore `lighthouse_report.json`
- [ ] Commit the uncommitted batch (split: importer/editor, PWA + service)

### Shopping List
- [x] Interactive list on `/` with real data + localStorage
- [ ] Offline recipe selection changes (queue + sync)
- [ ] Email/PDF/schedule UI on main page (still only on `/archive/shopping_list`)
- [ ] Mobile usability testing

### Recipe Import
- [x] Validation + retry with Gemini feedback (3 max), preview, progress UI
- [ ] Test on real URLs, including retry path

## Medium Priority

### Recipe Management
- [ ] Validate both recipe.yaml and recipe.md exist on load
- [ ] Better error handling (log errors, don't crash)
- [ ] Fix broken recipes:
  - moraccan_chickpea_and_apricot_tagine
  - gnocchi_bake (missing quantities)
  - firehouse_mac_n_cheese (missing quantities)
- [ ] Move enable/disable and min_period_weeks to web UI
- [ ] Rename "recipe list" to "saved recipes"

### Shopping List Features
- [ ] Scale quantities by number of people
- [ ] Custom unit rules (e.g., x tbsp butter = 1 stick)
- [ ] Spice blend lookup (expand to individual spices)
- [ ] Separate "Spices" section
- [ ] Better handling of mixed quantity types (1 bunch + unspecified)

### UI/UX
- [ ] Improve markdown formatting (headings more distinct)
- [ ] Remember last selected recipe on recipes page (cookie)
- [ ] Better mobile font consistency
- [ ] Format next schedule date (month/day names)

## Low Priority

- [ ] Support multiple meals per recipe (lunch + dinner)
- [ ] Print recipe functionality
- [ ] Mirror physical recipe book structure
- [ ] Refine random selection (specify N entrees + M sides)
- [ ] Recipe photos for missing images
- [ ] Shared drive for recipes (edit from any computer)

## Completed

- [x] PWA manifest, service worker, icons; SW scope/caching fixes (2026-10-10)
- [x] Service install scripts (2026-10-10)
- [x] Recipe data split to diehl_recipes repo (2026-10-10)
- [x] Recipe editor, Gemini import with validation, ingredient editor
- [x] Scheduled weekly emails, PDF generation
- [x] Recipe selection tracking
