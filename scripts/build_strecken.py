"""Baut data/strecken-bayern.geojson aus OpenStreetMap (Overpass).

Alle Eisenbahnstrecken-Relationen in Bayern (route=tracks und route=railway),
zusammengefasst je Streckennummer (ref), mit Name. Die Geometrie wird vereinfacht, damit die
Datei auf dem Handy schnell lädt.
"""
import json
import re
import math
import sys
import time
import urllib.parse
import urllib.request

QUERY = (
    '[out:json][timeout:900];'
    'area["ISO3166-2"="DE-BY"]->.by;'
    'relation["route"~"^(railway|tracks)$"](area.by);'
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


POINTS_QUERY = (
    '[out:json][timeout:900];'
    'area["ISO3166-2"="DE-BY"]->.by;'
    '('
    'node["railway"~"^(station|halt|junction|spur_junction|crossover|service_station|yard|site)$"](area.by);'
    'node["railway"="level_crossing"](area.by);'
    ');'
    'out;'
)
KM_QUERY = (
    '[out:json][timeout:900];'
    'area["ISO3166-2"="DE-BY"]->.by;'
    'node["railway"="milestone"](area.by);'
    'out;'
)
SKIP_STATION = {"subway", "monorail", "funicular", "tram"}


def fetch(query=QUERY):
    body = urllib.parse.urlencode({"data": query}).encode()
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


def rel_segments(rel):
    segs = []
    for m in rel.get("members", []):
        if m.get("type") != "way" or not m.get("geometry"):
            continue
        pts = [[round(g["lon"], 5), round(g["lat"], 5)] for g in m["geometry"]]
        pts = simplify(pts, TOLERANCE_M)
        if len(pts) >= 2:
            segs.append(pts)
    return segs


def build(data):
    groups = {}
    for rel in data.get("elements", []):
        if rel.get("type") != "relation":
            continue
        tags = rel.get("tags", {})
        ref = (tags.get("ref") or "").strip()
        if not ref:
            # Manche Strecken haben die Nummer nur im Namen, z. B. "5012 Bahnstrecke Kronach–Nordhalben"
            m = re.match(r"^(\d{4})\b", (tags.get("name") or "").strip())
            ref = m.group(1) if m else ""
        # Nur echte 4-stellige Streckennummern (VzG). Ohne Nummer sind es z. B. europäische
        # Fernverkehrsrouten wie die "Magistrale Européenne", 3-stellig sind Kursbuchstrecken.
        # Beide liegen auf den echten Strecken und würden sie überdecken.
        if not re.fullmatch(r"\d{4}", ref):
            continue
        groups.setdefault(ref, []).append(rel)

    features = []
    for key, rels in groups.items():
        # route=tracks ist in Deutschland die Infrastruktur-Strecke; route=railway nur, wenn es keine gibt
        tracks = [r for r in rels if r.get("tags", {}).get("route") == "tracks"]
        use = tracks or rels
        segs, seen = [], set()
        for rel in use:
            for seg in rel_segments(rel):
                k = (tuple(seg[0]), tuple(seg[-1]), len(seg))
                if k in seen:
                    continue
                seen.add(k)
                segs.append(seg)
        if not segs:
            continue
        names = [r.get("tags", {}).get("name") or r.get("tags", {}).get("description") for r in use]
        name = next((n for n in names if n), "Strecke")
        features.append({
            "type": "Feature",
            "properties": {
                "id": use[0]["id"],
                "ref": key if not key.startswith("id:") else "–",
                "name": name,
            },
            "geometry": {"type": "MultiLineString", "coordinates": segs},
        })
    features.sort(key=lambda f: (ref_key(f["properties"]["ref"]), f["properties"]["name"]))
    return {
        "type": "FeatureCollection",
        "attribution": "© OpenStreetMap-Mitwirkende, ODbL",
        "features": features,
    }


def build_points(data):
    feats = []
    for n in data.get("elements", []):
        if n.get("type") != "node":
            continue
        t = n.get("tags", {})
        kind = t.get("railway")
        if kind == "level_crossing":
            props = {"t": "bue"}
            if t.get("name"):
                props["n"] = t["name"]
        else:
            if t.get("station") in SKIP_STATION or t.get("subway") == "yes":
                continue
            if t.get("tram") == "yes" and t.get("train") != "yes":
                continue
            props = {"t": "bst", "k": kind}
            name = t.get("name") or t.get("railway:name")
            if name:
                props["n"] = name
            ril = t.get("railway:ref") or t.get("railway:ref:DB")
            if ril:
                props["r"] = ril
            if "n" not in props and "r" not in props:
                continue
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": "Point", "coordinates": [round(n["lon"], 5), round(n["lat"], 5)]}})
    return {"type": "FeatureCollection", "attribution": "© OpenStreetMap-Mitwirkende, ODbL", "features": feats}


def parse_km(v):
    if not v:
        return None
    v = v.strip().replace(",", ".").split(";")[0]
    if v.startswith("mi:"):
        return None
    try:
        if "+" in v:  # z. B. "12.3+45" -> 12.345
            a, b = v.split("+", 1)
            return round(float(a) + float(b) / 1000, 3)
        return float(v)
    except ValueError:
        return None


def build_km(data):
    feats = []
    for n in data.get("elements", []):
        t = n.get("tags", {})
        km = parse_km(t.get("railway:position:exact")) or parse_km(t.get("railway:position"))
        if km is None:
            continue
        km = round(km, 1)
        feats.append({"type": "Feature", "properties": {"k": int(km) if km == int(km) else km},
                      "geometry": {"type": "Point", "coordinates": [round(n["lon"], 5), round(n["lat"], 5)]}})
    return {"type": "FeatureCollection", "attribution": "© OpenStreetMap-Mitwirkende, ODbL", "features": feats}


def write(fc, out):
    import os
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(fc['features'])} Einträge geschrieben nach {out} ({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "data/strecken-bayern.geojson"
    pts_out = sys.argv[2] if len(sys.argv) > 2 else "data/punkte-bayern.geojson"
    pts = build_points(fetch(POINTS_QUERY))
    if len(pts["features"]) < 500:
        sys.exit(f"Nur {len(pts['features'])} Bahnanlagen gefunden, Datei wird nicht überschrieben")
    write(pts, pts_out)
    km_out = sys.argv[3] if len(sys.argv) > 3 else "data/km-bayern.geojson"
    km = build_km(fetch(KM_QUERY))
    if len(km["features"]) < 500:
        sys.exit(f"Nur {len(km['features'])} Kilometersteine gefunden, Datei wird nicht überschrieben")
    write(km, km_out)
    fc = build(fetch())
    if len(fc["features"]) < 50:
        sys.exit(f"Nur {len(fc['features'])} Strecken gefunden, Datei wird nicht überschrieben")
    import os
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(fc['features'])} Strecken geschrieben nach {out} ({os.path.getsize(out) // 1024} KB)")
