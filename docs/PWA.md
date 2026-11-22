# PWA, Offline, and Push

## Requirements

Service workers, install, and push only work in a secure context: HTTPS, or
`localhost`. On the phone that means the Tailscale URL
(`https://frank.<tailnet>.ts.net`), not `http://frank.local:5000`.

| File | Purpose |
|------|---------|
| `web/static/manifest.json` | Name, icons (`any` + `maskable`), scope `/` |
| `web/static/service-worker.js` | Caching and push. Served at `/service-worker.js` (scope `/`, `no-cache`) |
| `web/templates/base.html` | Registers the worker, shows the offline banner |

## Caching

| Requests | Strategy | Why |
|----------|----------|-----|
| `/static/*` | Stale-while-revalidate | Instant; versioned URLs make updates safe |
| `/recipes/*`, `/pending/*`, `/archived/*` | Stale-while-revalidate | Photos show instantly, replaced photos refresh next view |
| Pages, `/markdown/*`, other GETs | Network-first, cache after 4s | Fresh when online, usable on a weak store signal |
| `/import/`, `/chat/`, `/push/`, `/send_list`, `/schedule/`, PDF | Network-only | Meaningless offline |
| Non-GET | Not intercepted | |

**Precache on install:** the five main pages, manifest, vendored Bootstrap/jQuery/fonts, icons.

**Warm cache:** opening `/recipes_list` online posts `WARM_CACHE` with every saved
recipe's `/markdown/recipe/<name>` URL. The worker caches them, then parses each
response for `src="recipes/..."` and caches those photos. Result: the whole book,
with photos, readable offline. Recipes without a `recipe.md` are skipped.

Page navigations match the cache ignoring the query string, so
`/recipes_list?recipe=X` works offline.

### Asset versioning

Templates link own CSS/JS via `asset()`, which appends `?v=<file mtime>`. Without
it, the first load after a deploy got new HTML (network-first) with old CSS/JS
(stale-while-revalidate). Vendored files never change and are linked unversioned.

### Updating the worker

`install` calls `skipWaiting()` and `activate` claims clients and deletes every
cache not named `recipes-<CACHE_VERSION>`. Bump `CACHE_VERSION` when the
precache list or strategies change.

## Offline behavior

| Works | Needs network |
|-------|---------------|
| Shopping list (last loaded), check off/add/remove items | Selecting or removing recipes |
| Browsing and reading saved recipes with photos | Editing, import, chat |
| Weekly plan page (read-only) | Saving settings, push setup |

## Push notifications

```
Plan page --subscribe--> pushManager (browser) --endpoint+keys--> POST /push/subscribe
Weekly plan job --> PushStore.send_all --> pywebpush (VAPID-signed, aes128gcm)
  --> browser push service (FCM for Chrome) --> service worker 'push' --> notification
```

- **Keys:** `PushStore` creates a VAPID P-256 key pair on first use in
  `web/instance/vapid.json` (mode 600). Regenerating it invalidates every subscription.
- **Subscriptions:** `web/instance/push_subscriptions.json`, de-duplicated by endpoint,
  labeled "Chrome on Android" etc. A 404/410 from the push service removes the entry.
- **Payload:** `{title, body, url, tag}`, TTL 24h. `tag` collapses repeats.
- **Click:** focuses an open app window and navigates it to `url`, or opens one.
- Delivery goes through Google/Apple/Mozilla push servers, so the phone gets it without
  Tailscale running. Opening the app still needs Tailscale.
- iOS: only for apps added to the Home Screen (iOS 16.4+).

## Debugging

Desktop Chrome DevTools > Application: Service Workers (update on reload, push test),
Cache Storage, and Manifest. Headless Chromium denies notification permission, so
automated tests mock `webpush` instead of delivering.
