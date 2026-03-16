from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
TABLE_DATA_PATH = BASE_DIR / "table_data.json"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _get_nested(d: dict[str, Any], path: list[str]) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _normalize_entry(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None

    # Nouveau format (déjà OK)
    if any(
        k in entry
        for k in (
            "description_produit",
            "section_produit",
            "code_tarifaire",
            "classification_confidence",
        )
    ):
        out = {
            "description_produit": entry.get("description_produit"),
            "section_produit": entry.get("section_produit"),
            "code_tarifaire": entry.get("code_tarifaire"),
            "classification_confidence": entry.get("classification_confidence"),
            "statut_validation": entry.get("statut_validation") or "non_validé",
            "date_classification": entry.get("date_classification")
            or datetime.now(timezone.utc).isoformat(),
        }
        return out

    # Ancien format (product / classification)
    product = _as_dict(entry.get("product"))
    classification = _as_dict(entry.get("classification"))

    description = product.get("description")
    section = _get_nested(classification, ["section", "number"]) or classification.get(
        "section"
    )
    code = classification.get("code") or entry.get("hs_code") or entry.get("code")
    confidence = classification.get("confidence") or entry.get("confidence")

    if all(v is None for v in (description, section, code, confidence)):
        return None

    return {
        "description_produit": description,
        "section_produit": section,
        "code_tarifaire": code,
        "classification_confidence": confidence,
        "statut_validation": "non_validé",
        "date_classification": datetime.now(timezone.utc).isoformat(),
    }


def migrate(path: Path = TABLE_DATA_PATH) -> tuple[int, int]:
    if not path.exists():
        raise SystemExit(f"Fichier introuvable: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("table_data.json doit contenir une liste JSON.")

    migrated: list[dict[str, Any]] = []
    migrated_count = 0
    kept_count = 0

    for entry in raw:
        normalized = _normalize_entry(entry)
        if normalized is None:
            continue

        if "product" in (entry if isinstance(entry, dict) else {}):
            migrated_count += 1
        else:
            kept_count += 1

        migrated.append(normalized)

    path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2), encoding="utf-8")
    return migrated_count, kept_count


if __name__ == "__main__":
    m, k = migrate()
    print(f"[OK] Migration terminée: {m} entrées migrées, {k} entrées déjà au nouveau format.")
