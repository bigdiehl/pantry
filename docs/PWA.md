# Progressive Web App

## Quick start (phone)

1. `scripts/install_service.sh` then `scripts/setup_tailscale.sh` on the server
2. Install Tailscale on the phone, sign in to the same tailnet
3. Open `https://<host>.<tailnet>.ts.net/`
4. Android (Chrome): menu > Install app. iOS (Safari): Share > Add to Home Screen

**HTTPS is mandatory.** Service workers do not run on `http://<lan-ip>:5000`. Without them the app installs as a bookmark at best and nothing works offline. `localhost` is the only exception.

## Files

| File | Purpose |
|------|---------|
| `web/static/manifest.json` | App metadata, icons (`any` + `maskable`) |
| `web/static/service-worker.js` | Caching. Served at `/service-worker.js` so its scope is `/` |
| `web/static/icons/` | 72-512px icons |
| `web/templates/base.html` | Manifest link, SW registration, offline banner |

## Caching strategy

| Requests | Strategy |
|----------|----------|
| `/static/*`, CDN (Bootstrap, jQuery, fonts) | Stale-while-revalidate |
| `/recipes/*`, `/pending/*`, `/archived/*` (images) | Cache-first |
| Pages, `/markdown/*`, `/editor/*` GETs | Network-first, falls back to cache after 4s |
| `/import/*`, `/send_list`, `/schedule/*`, PDF | Network-only |

Precached on install: `/`, `/recipes_list`, site CSS/JS, CDN libs. Opening `/recipes_list` while online prefetches every saved recipe, so the whole book is readable offline.

## Offline

**Works:** shopping list (last loaded copy; checkboxes persist in localStorage), browse and read recipes, cached images.

**Needs network:** recipe selection, editing, import, email, schedule.

## Updating

Static files update on the next load after a change. To force-drop all caches, bump `CACHE_VERSION` in `service-worker.js`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| No install prompt | Not HTTPS. Use the `ts.net` URL |
| `tailscale serve` cert error | Enable MagicDNS + HTTPS Certificates in Tailscale admin > DNS |
| Offline shows "page has not been cached" | Visit that page once while online |
| Old UI after deploy | Reload twice, or bump `CACHE_VERSION` |
| Debugging | Desktop Chrome DevTools > Application > Service Workers / Cache Storage |
