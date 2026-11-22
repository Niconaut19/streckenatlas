"""Baut data/bayern-grenze.json: vereinfachter Umriss von Bayern (OSM-Relation 2145268).
Wird genutzt, um das bayerische Luftbild genau an der Landesgrenze abzuschneiden."""
import json, math, sys, urllib.parse, urllib.request, time
sys.path.insert(0, "scripts")
from build_strecken import simplify

Q = '[out:json][timeout:300];relation(2145268);out geom;'
EP = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]

def fetch():
    body = urllib.parse.urlencode({"data": Q}).encode()
    for u in EP:
        for _ in range(3):
            try:
                req = urllib.request.Request(u, data=body, headers={"User-Agent": "streckenatlas-build (github.com/Niconaut19/streckenatlas)"})
                with urllib.request.urlopen(req, timeout=400) as r:
                    return json.load(r)
            except Exception as e:
                print(e, file=sys.stderr); time.sleep(20)
    sys.exit("Overpass nicht erreichbar")

def rings(ways):
    ways = [[(round(p["lon"], 6), round(p["lat"], 6)) for p in w] for w in ways]
    out = []
    while ways:
        ring = ways.pop(0)
        while ring[0] != ring[-1]:
            for i, w in enumerate(ways):
                if w[0] == ring[-1]: ring += w[1:]
                elif w[-1] == ring[-1]: ring += w[::-1][1:]
                elif w[-1] == ring[0]: ring = w + ring[1:]
                elif w[0] == ring[0]: ring = w[::-1] + ring[1:]
                else: continue
                ways.pop(i); break
            else:
                break
        if ring[0] == ring[-1] and len(ring) > 3: out.append(ring)
    return out

rel = next(e for e in fetch()["elements"] if e["type"] == "relation")
outer = [m["geometry"] for m in rel["members"] if m["type"] == "way" and m.get("role") == "outer" and m.get("geometry")]
res = []
for r in rings(outer):
    s = simplify([list(p) for p in r], 40.0)
    if len(s) >= 4: res.append([[round(x, 5), round(y, 5)] for x, y in s])
res.sort(key=len, reverse=True)
print("Ringe:", [len(r) for r in res])
if not res or len(res[0]) < 300: sys.exit("Umriss unvollständig")
with open("data/bayern-grenze.json", "w") as f:
    json.dump(res, f, separators=(",", ":"))
