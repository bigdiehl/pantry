# Progressive Web App

## Features

- Install to home screen (iOS/Android)
- Offline support for browsing recipes
- Native app feel (no browser UI)

## Files

- `web/static/manifest.json` - PWA metadata
- `web/static/service-worker.js` - Offline caching
- `web/static/icons/` - App icons (72px-512px)

## Caching Strategy

**Cache-first:** Static assets, images, recipe files
**Network-first:** API calls, shopping list, recipe data
**Network-only:** Import, email, schedule (require internet)

## Installation

**Android (Chrome):**
1. Visit app in Chrome
2. Menu → "Add to Home screen"
3. Confirm

**iOS (Safari):**
1. Visit app in Safari
2. Share → "Add to Home Screen"
3. Confirm

## Offline Capabilities

**Available:** Browse recipes, view images (if cached), read shopping list, navigate pages

**Unavailable:** Import recipes, send email, update schedule, toggle selection

## Testing

**Service worker:**
DevTools → Application → Service Workers

**Offline mode:**
DevTools → Network → Offline

**Cache:**
DevTools → Application → Cache Storage

## Production Requirements

**HTTPS required** (except localhost). Options:
- Tailscale (works without HTTPS for private access)
- Cloudflare Tunnel (automatic HTTPS)
- nginx + Let's Encrypt

## Troubleshooting

**Service worker not registering:** Check console errors, verify HTTPS in production

**Offline not working:** Check cache storage in DevTools

**iOS install not appearing:** Must use Safari (not Chrome on iOS)

**Cache not updating:** Increment version in service-worker.js:
```javascript
const CACHE_NAME = 'recipes-v2';  // Change v1 → v2
```
