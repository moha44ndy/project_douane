import json
import time
import urllib.request

API = "http://127.0.0.1:8000/classify"
TESTS = {
    "TEST 2": """Produit : smartphone reconditionné

Modifications :
- écran remplacé (pièce générique)
- batterie non OEM
- coque plastique changée

Fonctions :
- téléphonie
- internet
- GPS
- 5G""",
    "TEST 10": """Produit : dispositif électronique multifonction adaptable usage industriel

Composition :
- plastique 40 %
- électronique 30 %
- métal 20 %
- batterie 10 %""",
}

for tid, query in TESTS.items():
    print(f"=== {tid} ===")
    t0 = time.time()
    try:
        body = json.dumps({"query": query}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            API, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = json.loads(json.loads(resp.read().decode("utf-8"))["raw"])
        elapsed = round(time.time() - t0, 1)
        items = raw.get("classifications") or []
        print(f"OK en {elapsed}s — {len(items)} ligne(s)")
        for item in items[:6]:
            code = item.get("hs_code")
            conf = item.get("confidence")
            desc = (item.get("description") or "")[:90]
            print(f"  • {code} | {conf}% | {desc}")
        if len(items) > 6:
            print(f"  … +{len(items) - 6} lignes")
    except Exception as exc:
        print(f"ERREUR en {round(time.time() - t0, 1)}s: {exc}")
    print()
