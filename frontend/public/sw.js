// Vidya Pramaan service worker: installable app, and the QR verification page keeps working offline.
// Only the app shell and static assets are cached. API responses (student data) are never cached.
const CACHE = "vp-shell-v2";
const SHELL = ["/", "/verify", "/manifest.webmanifest", "/favicon.svg", "/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  if (e.request.mode === "navigate") {
    // Network first for pages, so users always get the current app; fall back to the cached shell offline.
    e.respondWith(fetch(e.request).catch(() => caches.match("/verify").then((r) => r || caches.match("/"))));
    return;
  }
  if (url.pathname.startsWith("/assets/") || SHELL.includes(url.pathname)) {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
      return res;
    })));
  }
});
