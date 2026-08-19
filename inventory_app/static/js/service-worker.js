/* StockSetu Service Worker — Offline POS Support
   Caches:
   - Static assets (CSS, JS, fonts, icons)
   - Product search API responses (stale-while-revalidate)
   - Employee list API (stale-while-revalidate)
   Does NOT cache: billing/create, payment, refund (must be online)
*/

const CACHE_NAME = 'stocksetu-pos-v1';
const STATIC_ASSETS = [
  '/',
  '/static/css/main.css',
  '/static/js/app-base.js',
  '/static/js/main.js',
  '/static/js/toasts.js',
  '/static/js/pos-app.js',
  '/static/img/logo.svg',
];

/* API routes safe to cache (read-only, non-sensitive) */
const CACHEABLE_API = [
  '/api/products/search',
  '/api/employees/list',
  '/api/cart/load',
];

/* Install — pre-cache critical static assets */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

/* Activate — clean old caches */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

/* Fetch — Network-first for navigation, stale-while-revalidate for APIs, cache-first for static */
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  /* Skip non-GET, skip chrome-extension, skip mutating APIs */
  if (request.method !== 'GET') return;

  /* Navigation requests: network-first (so user always gets latest HTML) */
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/') || new Response('Offline', { status: 503 }))
    );
    return;
  }

  /* Read-only API routes: stale-while-revalidate */
  if (CACHEABLE_API.some((p) => url.pathname.startsWith(p))) {
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cachedResponse = await cache.match(request);
        const fetchPromise = fetch(request).then((networkResponse) => {
          if (networkResponse.ok) cache.put(request, networkResponse.clone());
          return networkResponse;
        }).catch(() => cachedResponse);
        return cachedResponse || fetchPromise;
      })
    );
    return;
  }

  /* Static assets: cache-first */
  if (url.pathname.startsWith('/static/') || url.hostname === 'fonts.googleapis.com' || url.hostname === 'cdn.jsdelivr.net') {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((c) => c.put(request, clone));
        }
        return response;
      }))
    );
    return;
  }

  /* Everything else: network-first */
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});
