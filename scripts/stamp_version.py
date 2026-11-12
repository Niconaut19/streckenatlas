"""Schreibt die App-Version in index.html und version.json.

Die Version ist ein Fingerabdruck des Inhalts von index.html (ohne die Versionszeile selbst).
Sie ändert sich also nur, wenn sich an der App wirklich etwas geändert hat.
Vor jedem Einspielen ausführen: python3 scripts/stamp_version.py
"""
import datetime, hashlib, json, pathlib, re

root = pathlib.Path(__file__).resolve().parent.parent
idx = root / "index.html"
html = idx.read_text(encoding="utf-8")
pat = re.compile(r'const APP_VERSION="[^"]*", APP_DATE="[^"]*";')
if not pat.search(html):
    raise SystemExit("Versionszeile in index.html nicht gefunden")
neutral = pat.sub('const APP_VERSION="", APP_DATE="";', html)
ver = hashlib.sha256(neutral.encode("utf-8")).hexdigest()[:10]
old = json.loads((root / "version.json").read_text()) if (root / "version.json").exists() else {}
date = old.get("date") if old.get("v") == ver else datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
idx.write_text(pat.sub(f'const APP_VERSION="{ver}", APP_DATE="{date}";', html), encoding="utf-8")
(root / "version.json").write_text(json.dumps({"v": ver, "date": date}) + "\n")
print(ver, date)
