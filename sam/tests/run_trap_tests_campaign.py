"""Campagne des 10 cas pièges SH — appelle POST /classify et résume les résultats."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

TESTS: list[dict[str, str]] = [
    {
        "id": "TEST 1",
        "name": "Chaussure de sécurité",
        "query": """Produit : chaussure de sécurité industrielle

Composition :
- 40 % cuir bovin (tige)
- 35 % textile technique
- 20 % caoutchouc (semelle)
- 5 % acier (embout)

Norme : EN ISO 20345
Usage : protection chantier BTP""",
        "trap": "Cuir vs textile vs caoutchouc vs fonction protection ?",
    },
    {
        "id": "TEST 2",
        "name": "Smartphone reconditionné",
        "query": """Produit : smartphone reconditionné

Modifications :
- écran remplacé (pièce générique)
- batterie non OEM
- coque plastique changée

Fonctions :
- téléphonie
- internet
- GPS
- 5G""",
        "trap": "Neuf / usagé / pièce détachée ?",
    },
    {
        "id": "TEST 3",
        "name": "Drone hybride agricole",
        "query": """Produit : drone agricole professionnel

Fonctions :
- pulvérisation pesticides
- cartographie thermique
- surveillance cultures
- prise de vue aérienne

Composition :
- aluminium 35 %
- carbone 20 %
- électronique 25 %
- batterie lithium 15 %
- caméra 5 %""",
        "trap": "Drone agricole vs caméra vs pulvérisation vs prise de vue ?",
    },
    {
        "id": "TEST 4",
        "name": "Kit médical d'urgence",
        "query": """Produit : kit médical d'urgence scellé

Contenu :
- seringues stériles
- compresses
- gants latex
- antiseptique
- ciseaux chirurgicaux
- boîte plastique

Vendu comme ensemble unique""",
        "trap": "Assortiment RGI 3(b) vs lignes séparées ?",
    },
    {
        "id": "TEST 5",
        "name": "Imprimante multifonction",
        "query": """Produit : imprimante multifonction

Fonctions :
- impression
- scanner
- photocopie
- fax

Technologie :
- jet d'encre
- Wi-Fi
- écran tactile""",
        "trap": "Fonction principale unique ou appareil composite ?",
    },
    {
        "id": "TEST 6",
        "name": "Valise connectée",
        "query": """Produit : valise connectée intelligente

Composition :
- polycarbonate 50 %
- aluminium 20 %
- tissu 15 %
- électronique GPS 15 %

Fonctions :
- GPS tracking
- verrouillage digital
- USB charging
- balance intégrée""",
        "trap": "Valise classique ou appareil électronique ?",
    },
    {
        "id": "TEST 7",
        "name": "Veste militaire tactique",
        "query": """Produit : veste militaire tactique

Composition :
- kevlar 30 %
- nylon 40 %
- coton 20 %
- membrane imperméable 10 %

Fonctions :
- anti-coupure
- anti-feu
- imperméable
- camouflage""",
        "trap": "Vêtement textile ou équipement de protection ?",
    },
    {
        "id": "TEST 8",
        "name": "Machine industrielle en kit",
        "query": """Produit importé en kit :
- moteur électrique
- pompe hydraulique
- châssis acier
- tableau de commande électronique""",
        "trap": "Machine complète ou pièces détachées ?",
    },
    {
        "id": "TEST 9",
        "name": "Coffret cadeau mixte",
        "query": """Produit : coffret cadeau premium

Contenu :
- bouteille de vin
- verre cristal
- tire-bouchon acier
- coffret bois

Vendu ensemble pour cadeau premium""",
        "trap": "Alcool vs verre vs coffret vs assortiment ?",
    },
    {
        "id": "TEST 10",
        "name": "Description vague",
        "query": """Produit : dispositif électronique multifonction adaptable usage industriel

Composition :
- plastique 40 %
- électronique 30 %
- métal 20 %
- batterie 10 %""",
        "trap": "Description volontairement vague — test incertitude",
    },
]


def classify(query: str, timeout: int = 180) -> dict:
    body = json.dumps({"query": query}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/classify",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    raw = payload.get("raw") or ""
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def summarize(data: dict) -> dict:
    items = data.get("classifications") or []
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "hs_code": item.get("hs_code"),
                "confidence": item.get("confidence"),
                "status": item.get("classification_status"),
                "risk": (item.get("risk_assessment") or {}).get("risk_level"),
                "description": (item.get("description") or "")[:120],
                "justification": (item.get("justification") or "")[:400],
            }
        )
    narrative = (data.get("narrative") or "")[:500]
    return {"count": len(rows), "rows": rows, "narrative": narrative}


def main() -> int:
    print(f"API: {API_BASE}/classify\n")
    results: list[dict] = []
    for test in TESTS:
        print(f"=== {test['id']} — {test['name']} ===")
        print(f"Piège: {test['trap']}")
        t0 = time.time()
        try:
            data = classify(test["query"])
            elapsed = round(time.time() - t0, 1)
            summary = summarize(data)
            print(f"OK en {elapsed}s — {summary['count']} ligne(s)")
            for row in summary["rows"]:
                print(
                    f"  • {row['hs_code']} | conf={row['confidence']}% | "
                    f"statut={row['status']} | risque={row['risk']}"
                )
                print(f"    desc: {row['description']}")
            if summary["narrative"]:
                print(f"  narrative: {summary['narrative'][:200]}…")
            results.append({"test": test["id"], "ok": True, "elapsed_s": elapsed, **summary})
        except Exception as exc:
            elapsed = round(time.time() - t0, 1)
            print(f"ERREUR en {elapsed}s: {exc}")
            results.append({"test": test["id"], "ok": False, "error": str(exc), "elapsed_s": elapsed})
        print()
    out_path = os.path.join(os.path.dirname(__file__), "trap_tests_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Résultats sauvegardés: {out_path}")
    failed = sum(1 for r in results if not r.get("ok"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
