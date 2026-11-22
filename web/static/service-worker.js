// Service Worker for Recipe Manager PWA
// Served from /service-worker.js (see app.py) so its scope covers the whole app.
// Bump CACHE_VERSION to force every client to drop its old cache.

const CACHE_VERSION = 'v2';
const CACHE_NAME = `recipes-${CACHE_VERSION}`;

// Network-first requests fall back to cache after this long. Keeps the app
// usable on a weak signal (e.g. inside a grocery store).
const NETWORK_TIMEOUT_MS = 4000;

const PRECACHE_URLS = [
  '/',
  '/recipes_list',
  '/static/manifest.json',
  '/static/css/style.css',
  '/static/scripts/recipe_grouping.js',
  '/static/scripts/recipes_list.js',
  '/static/scripts/shopping_list.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js',
  'https://code.jquery.com/jquery-3.7.0.min.js',
];

// Features that only make sense online. Never cached.
const NETWORK_ONLY_PREFIXES = [
  '/import/',
  '/send_list',
  '/schedule/',
  '/download_shopping_list_pdf',
];

// Recipe images and files. Rarely change, so serve from cache.
const CACHE_FIRST_PREFIXES = ['/recipes/', '/pending/', '/archived/'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    cacheUrls(PRECACHE_URLS).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (!url.protocol.startsWith('http')) return;

  const sameOrigin = url.origin === self.location.origin;
  const path = url.pathname;

  if (sameOrigin && NETWORK_ONLY_PREFIXES.some((p) => path.startsWith(p))) {
    event.respondWith(networkOnly(request));
  } else if (!sameOrigin || path.startsWith('/static/')) {
    event.respondWith(staleWhileRevalidate(request));
  } else if (CACHE_FIRST_PREFIXES.some((p) => path.startsWith(p))) {
    event.respondWith(cacheFirst(request));
  } else {
    event.respondWith(networkFirst(request));
  }
});

// Pages send {type: 'WARM_CACHE', urls: [...]} to prefetch content for offline use.
self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  } else if (data.type === 'WARM_CACHE' && Array.isArray(data.urls)) {
    event.waitUntil(cacheUrls(data.urls));
  }
});

// Cross-origin CDN assets without a crossorigin attribute come back opaque
// (status 0). They are still usable, so cache them too.
function isCacheable(response) {
  return response && (response.ok || response.type === 'opaque');
}

// Fetch and cache each URL independently; one failure must not abort the rest.
async function cacheUrls(urls) {
  const cache = await caches.open(CACHE_NAME);
  await Promise.all(urls.map(async (u) => {
    try {
      const sameOrigin = new URL(u, self.location.origin).origin === self.location.origin;
      const response = await fetch(u, sameOrigin ? {} : { mode: 'no-cors' });
      if (isCacheable(response)) await cache.put(u, response);
    } catch (err) {
      console.warn('[ServiceWorker] Precache failed:', u, err);
    }
  }));
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (isCacheable(response)) cache.put(request, response.clone());
    return response;
  } catch (err) {
    return offlineResponse(request);
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (isCacheable(response)) cache.put(request, response.clone());
      return response;
    })
    .catch(() => null);
  return cached || (await network) || offlineResponse(request);
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const network = fetch(request).then((response) => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  });
  network.catch(() => {}); // Rejection is handled below; silence the unhandled warning.

  // Race the network against a timeout; only fall back if a cached copy exists.
  const timeout = new Promise((resolve) => setTimeout(resolve, NETWORK_TIMEOUT_MS));
  try {
    const winner = await Promise.race([network, timeout]);
    if (winner) return winner;
    const cached = await matchCached(cache, request);
    if (cached) return cached;
    return await network;
  } catch (err) {
    const cached = await matchCached(cache, request);
    return cached || offlineResponse(request);
  }
}

async function networkOnly(request) {
  try {
    return await fetch(request);
  } catch (err) {
    return new Response('This feature requires an internet connection', {
      status: 503,
      statusText: 'Service Unavailable',
    });
  }
}

// Page navigations ignore the query string so e.g. /recipes_list?recipe=X
// still finds the cached /recipes_list.
function matchCached(cache, request) {
  return cache.match(request, { ignoreSearch: request.mode === 'navigate' });
}

function offlineResponse(request) {
  if (request.mode === 'navigate') {
    return new Response(
      '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">' +
      '<title>Offline</title><body style="font-family:sans-serif;padding:2rem">' +
      '<h1>Offline</h1><p>This page has not been cached yet. ' +
      '<a href="/">Shopping list</a> &middot; <a href="/recipes_list">Recipes</a></p>',
      { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
  return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
}
