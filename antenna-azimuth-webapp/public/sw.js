/**
 * Minimal app-shell service worker.
 *
 * Deliberately does NOT cache satellite tiles or API responses: tiles are
 * large and the shadow probe must reflect live imagery. This only keeps the
 * shell reachable so the app opens (and shows its offline state) when a
 * field connection drops.
 */
const CACHE = "azimuth-shell-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  // Never intercept the API or cross-origin tile requests.
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  event.respondWith(
    fetch(request)
      .then((resp) => {
        if (resp.ok && request.mode === "navigate") {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(request, copy));
        }
        return resp;
      })
      .catch(() => caches.match(request).then((hit) => hit ?? caches.match("/")))
  );
});
