/* Service Worker: App offline verfügbar machen, Kartenteile speichern, Mitteilungen öffnen */
const SHELL = "sa-shell-v2";        // App-Dateien und Bibliotheken
const DATA = "sa-data-v1";          // Strecken-, Bahnanlagen- und Kilometerdaten
const SAVED = "sa-tiles-saved";     // gezielt für offline gespeicherte Kartenteile (bleiben)
const RUNTIME = "sa-tiles-rt";      // beim Anschauen gemerkte Kartenteile (werden begrenzt)
const RUNTIME_MAX = 1000;   // ca. 50 MB, älteste werden zuerst entfernt

const SHELL_URLS = [
  "./", "./manifest.webmanifest", "./icons/icon-192.png", "./icons/apple-touch-icon.png", "./icons/favicon-32.png",
  "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js",
  "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css",
  "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.58.0/dist/umd/supabase.js"
];
const DATA_URLS = ["./data/strecken-bayern.geojson", "./data/punkte-bayern.geojson", "./data/km-bayern.geojson"];

self.addEventListener("install", e => {
  e.waitUntil((async () => {
    const s = await caches.open(SHELL), d = await caches.open(DATA);
    await Promise.allSettled([...SHELL_URLS.map(u => s.add(u)), ...DATA_URLS.map(u => d.add(u))]);
    await self.skipWaiting();
  })());
});
self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k.startsWith("sa-shell-") && k !== SHELL) await caches.delete(k);
  await self.clients.claim();
})()));

/* Luftbild Bayern kommt als WMS mit Koordinaten-Ausschnitt. Für den Speicher wird daraus
   ein fester Schlüssel z/x/y, damit gespeicherte und angezeigte Teile sicher zusammenpassen. */
const R = 20037508.342789244;
function tileKey(url) {
  const u = new URL(url);
  if (u.hostname === "geoservices.bayern.de") {
    const bb = (u.searchParams.get("bbox") || u.searchParams.get("BBOX") || "").split(",").map(Number);
    if (bb.length !== 4 || bb.some(isNaN)) return null;
    const w = bb[2] - bb[0], z = Math.round(Math.log2(2 * R / w));
    const x = Math.round((bb[0] + R) / w), y = Math.round((R - bb[3]) / w);
    return `https://tilecache.streckenatlas/dop/${z}/${x}/${y}`;
  }
  if (u.hostname === "tiles.openfreemap.org" && /\.pbf$/.test(u.pathname)) {
    const m = u.pathname.match(/\/(\d+)\/(\d+)\/(\d+)\.pbf$/);
    return m ? `https://tilecache.streckenatlas/omt/${m[1]}/${m[2]}/${m[3]}` : null;
  }
  return null;
}
self.tileKey = tileKey;

async function trimRuntime() {
  const c = await caches.open(RUNTIME), keys = await c.keys();
  for (let i = 0; i < keys.length - RUNTIME_MAX; i++) await c.delete(keys[i]);
}
let putCount = 0;

async function tileFetch(req, key) {
  const hit = (await caches.match(key, { cacheName: SAVED })) || (await caches.match(key, { cacheName: RUNTIME }));
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) {
    const c = await caches.open(RUNTIME);
    await c.put(key, res.clone());
    if (++putCount % 200 === 0) trimRuntime();
  }
  return res;
}
async function networkFirst(req, cacheName, timeoutMs, matchOpts) {
  const c = await caches.open(cacheName);
  try {
    // cache: "no-cache" = immer beim Server nachfragen, ob es eine neuere Fassung gibt
    const res = await Promise.race([fetch(req, { cache: "no-cache" }), new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), timeoutMs))]);
    if (res.ok) c.put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await c.match(req, matchOpts);
    if (hit) return hit;
    throw err;
  }
}
async function staleWhileRevalidate(req, cacheName) {
  const c = await caches.open(cacheName);
  const hit = await c.match(req);
  const net = fetch(req).then(res => { if (res.ok || res.type === "opaque") c.put(req, res.clone()); return res; }).catch(() => null);
  return hit || (await net) || Response.error();
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.hostname.endsWith("supabase.co")) return;                       // Anmeldung und Daten: immer live

  const key = tileKey(req.url);
  if (key) { e.respondWith(tileFetch(req, key)); return; }

  if (url.origin === self.location.origin) {
    if (req.mode === "navigate" || url.pathname.endsWith("/") || url.pathname.endsWith("/index.html")) {
      // App-Seite: zuerst aus dem Netz (damit Updates ankommen), ohne Netz die gespeicherte
      e.respondWith(networkFirst(new Request("./", { credentials: "same-origin" }), SHELL, 5000, { ignoreSearch: true })
        .catch(() => caches.match("./", { ignoreSearch: true })));
      return;
    }
    if (url.pathname.includes("/data/")) { e.respondWith(networkFirst(req, DATA, 8000, { ignoreSearch: true })); return; }
    e.respondWith(staleWhileRevalidate(req, SHELL));
    return;
  }
  // Bibliotheken, Schriften, Symbole und Kartenbeschreibung
  if (["unpkg.com", "cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com", "fonts.openmaptiles.org"].includes(url.hostname)
      || (url.hostname === "tiles.openfreemap.org" && url.pathname.startsWith("/sprites/"))) {
    e.respondWith(staleWhileRevalidate(req, SHELL)); return;
  }
  if (url.hostname === "tiles.openfreemap.org" && url.pathname === "/planet") {
    e.respondWith(networkFirst(req, SHELL, 5000)); return;
  }
});

self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil((async () => {
    const all = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const c of all) { if ("focus" in c) return c.focus(); }
    return self.clients.openWindow("./");
  })());
});
