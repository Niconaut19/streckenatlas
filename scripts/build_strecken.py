"""Baut data/strecken-bayern.geojson aus OpenStreetMap (Overpass).

Alle Eisenbahnstrecken-Relationen (route=railway) in Bayern, mit
Streckennummer (ref) und Name. Die Geometrie wird vereinfacht, damit die
Datei auf dem Handy schnell lädt.
"""
import json
import math
import sys
import time
import urllib.parse
import urllib.request

QUERY = (
    '[out:json][timeout:900];'
    'area["ISO3166-2"="DE-BY"]->.by;'
    'relation["route"="railway"](area.by);'
    'out geom;'
)
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
TOLERANCE_M = 4.0
LAT0 = 48.9
KX = 111320 * math.cos(math.radians(LAT0))
KY = 110540


def fetch():
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    for url in ENDPOINTS:
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=body, headers={
                    "User-Agent": "streckenatlas-build (github.com/Niconaut19/streckenatlas)"})
                with urllib.request.urlopen(req, timeout=1000) as r:
                    return json.load(r)
            except Exception as e:  # noqa: BLE001
                print(f"Versuch {attempt + 1} bei {url} fehlgeschlagen: {e}", file=sys.stderr)
                time.sleep(30)
    sys.exit("Overpass nicht erreichbar")


def simplify(pts, tol):
    """Douglas-Peucker auf [lon, lat]-Punkten, Toleranz in Metern."""
    if len(pts) < 3:
        return pts
    xy = [(p[0] * KX, p[1] * KY) for p in pts]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = xy[a]
        bx, by = xy[b]
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        best_d, best_i = -1.0, -1
        for i in range(a + 1, b):
            px, py = xy[i]
            if length2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
                d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > best_d:
                best_d, best_i = d, i
        if best_d > tol:
            keep[best_i] = True
            stack.append((a, best_i))
            stack.append((best_i, b))
    return [p for p, k in zip(pts, keep) if k]


def ref_key(ref):
    digits = "".join(c for c in ref if c.isdigit())
    return (int(digits) if digits else 99999, ref)


def build(data):
    features = []
    for rel in data.get("elements", []):
        if rel.get("type") != "relation":
            continue
        tags = rel.get("tags", {})
        segs = []
        for m in rel.get("members", []):
            if m.get("type") != "way" or not m.get("geometry"):
                continue
            pts = [[round(g["lon"], 5), round(g["lat"], 5)] for g in m["geometry"]]
            pts = simplify(pts, TOLERANCE_M)
            if len(pts) >= 2:
                segs.append(pts)
        if not segs:
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "id": rel["id"],
                "ref": tags.get("ref", "–"),
                "name": tags.get("name") or tags.get("description") or "Strecke",
            },
            "geometry": {"type": "MultiLineString", "coordinates": segs},
        })
    features.sort(key=lambda f: (ref_key(f["properties"]["ref"]), f["properties"]["name"]))
    return {
        "type": "FeatureCollection",
        "attribution": "© OpenStreetMap-Mitwirkende, ODbL",
        "features": features,
    }


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "data/strecken-bayern.geojson"
    fc = build(fetch())
    if len(fc["features"]) < 50:
        sys.exit(f"Nur {len(fc['features'])} Strecken gefunden, Datei wird nicht überschrieben")
    import os
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(fc['features'])} Strecken geschrieben nach {out} ({os.path.getsize(out) // 1024} KB)")
