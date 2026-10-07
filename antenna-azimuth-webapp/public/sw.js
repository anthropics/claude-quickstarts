/** Public assets only. User data and app HTML always use the network. */
const CACHE = "azimuth-shell-v2";
const PUBLIC_ASSETS = new Set(["/manifest.webmanifest", "/icon-192.png", "/icon-512.png"]);
const OFFLINE_PAGE = "<!doctype html><html lang=\"cs\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Azimuth – bez připojení</title><body><main><h1>Chybí připojení</h1><p>Připojte se k internetu a obnovte stránku. Projekty a PDF se do offline cache neukládají.</p></main></body></html>";

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(key => key.startsWith("azimuth-shell-") && key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const publicAsset = !url.search && PUBLIC_ASSETS.has(url.pathname);
  if (publicAsset) {
    event.respondWith(fetch(request).then(response => {
      if (response.ok && response.type !== "opaque") {
        const copy = response.clone();
        event.waitUntil(caches.open(CACHE).then(cache => cache.put(request, copy)));
      }
      return response;
    }).catch(async () => {
      const cache = await caches.open(CACHE);
      return (await cache.match(request)) ?? Response.error();
    }));
    return;
  }
  // Do not intercept scripts, PDF, API/auth/project requests or cross-origin data.
  if (request.mode !== "navigate" || url.pathname !== "/" || url.search) return;
  event.respondWith(fetch(request).catch(() => new Response(OFFLINE_PAGE, {
    status: 503,
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
  })));
});
