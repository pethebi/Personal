// Food Capture service worker: cache the app shell so it opens offline. Bump VERSION on changes.
const VERSION = "fc-v1";
const SHELL = ["./", "index.html", "app.js", "manifest.webmanifest", "icon.svg", "icon-180.png"];
self.addEventListener("install", e => e.waitUntil(caches.open(VERSION).then(c => Promise.all(SHELL.map(u => c.add(u).catch(() => {})))).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return; // never touch GitHub API calls
  // network first (fresh app when online), cache fallback (offline)
  e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(VERSION).then(x => x.put(e.request, c)); return r; })
    .catch(() => caches.match(e.request, { ignoreSearch: true }).then(h => h || caches.match("index.html"))));
});
