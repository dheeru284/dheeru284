// Minimal offline shell. Never caches API responses (they can contain personal data).
const CACHE = "hn-shell-v1";
const SHELL = ["/", "/safety", "/manifest.webmanifest"];
self.addEventListener("install", (e) => e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", (e) => e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).catch(() => caches.match("/safety").then((r) => r ?? new Response("Offline. In an emergency call 112.", { headers: { "content-type": "text/plain" } }))));
  } else if (url.pathname.startsWith("/_next/static/")) {
    e.respondWith(caches.match(e.request).then((hit) => hit ?? fetch(e.request).then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); return res; })));
  }
});
