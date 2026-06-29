// Service worker — estratégia NETWORK-FIRST para o app sempre mostrar a versão
// mais recente (corrige o "não atualiza no celular"). Cai no cache só offline.
const CACHE = "fisiocoach-v3";

self.addEventListener("install", () => {
  self.skipWaiting(); // ativa a nova versão imediatamente
});

self.addEventListener("activate", (e) => {
  // apaga TODOS os caches antigos para forçar conteúdo novo
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return; // nunca mexe em uploads/análises
  e.respondWith(
    fetch(req)
      .then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return resp;
      })
      .catch(() => caches.match(req)) // offline: usa o cache se existir
  );
});
