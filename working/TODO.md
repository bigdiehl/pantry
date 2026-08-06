# Project TODOs

## High Priority

### PWA for Phone
- [x] Basic PWA setup (manifest, service worker, icons)
- [ ] Test PWA install on phone
- [ ] Verify offline mode works reliably
- [ ] Test shopping list caching on mobile

### Remote Access
- [ ] Decision: Tailscale vs Cloudflare Tunnel vs other
- [ ] Setup chosen solution
- [ ] Test HTTPS for PWA requirements
- [ ] Document access method

### Interactive Shopping List
- [x] Demo prototype built (shopping_demo.html)
- [ ] Integrate with real shopping list API
- [ ] Add localStorage persistence
- [ ] Offline change queueing + sync when online
- [ ] Mobile usability testing

### Recipe Import Verification
- [ ] Add validation step after Gemini extraction
- [ ] Check required fields present (name, ingredients, instructions)
- [ ] Validate ingredient format (food name + quantity)
- [ ] Feed validation errors back to Gemini for retry
- [ ] Limit retry attempts (3 max?)
- [ ] Preview/edit before saving to pending/

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

- [x] PWA manifest and service worker
- [x] App icons generated
- [x] Shopping demo prototype
- [x] Recipe editor with YAML + markdown
- [x] Gemini-based recipe import
- [x] Scheduled weekly emails
- [x] PDF generation and email
- [x] Recipe selection tracking
