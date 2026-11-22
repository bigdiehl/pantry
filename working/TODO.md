# Project TODOs

## High Priority

### Server (frank.local) / PWA on Phone
- [ ] Clone pantry + diehl_recipes on frank, run `scripts/install_service.sh` (retires frank_web_server.service)
- [ ] Install Tailscale on frank, run `scripts/setup_tailscale.sh` (MagicDNS + HTTPS certs on in admin console)
- [ ] Install from `https://frank.<tailnet>.ts.net` on phone
- [ ] Verify offline: shopping list, recipe list, recipe content, images
- [ ] Fix Lighthouse items: color contrast, heading order, meta description
- [ ] Decide how web-UI recipe edits on frank get committed to diehl_recipes

### Repo Split / Git
- [ ] Delete `~/projects/recipes_prefilter_20261122.bundle` and `~/projects/recipes_git_backup_20261122` once confirmed
- [ ] Remove old `/srv/samba_share/recipes_app` on frank once pantry is running

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

- [x] Purged recipe data from history, consolidated on master, renamed repo to pantry (2026-11-22)
- [x] diehl_recipes pushed to GitHub (2026-11-22)
- [x] pytest suite, GitHub Actions CI, auto-deploy timer (2026-11-22)
- [x] PWA manifest, service worker, icons; SW scope/caching fixes (2026-10-10)
- [x] Service install scripts (2026-10-10)
- [x] Recipe data split to diehl_recipes repo (2026-10-10)
- [x] Recipe editor, Gemini import with validation, ingredient editor
- [x] Scheduled weekly emails, PDF generation
- [x] Recipe selection tracking
