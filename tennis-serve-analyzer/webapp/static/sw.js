// Service worker mínimo: torna o app instalável (PWA) e dá um cache básico
// dos arquivos estáticos. As análises (POST /analyze) sempre vão à rede.
const CACHE = "fisiocoach-v1";
const ASSETS = [
  "/",
  "/static/style.css",
  "/static/camera.js",
  "/static/logo.png",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/apple-touch-icon.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  // nunca cacheia POST (uploads/análises)
  if (req.method !== "GET") return;
  e.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).catch(() => hit))
  );
});
