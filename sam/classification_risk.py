"""Indice de risque de contestation pour les classifications tarifaires."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_UNCERTAINTY_KEYWORDS = (
    "incertain",
    "plusieurs position",
    "plusieurs code",
    "hypothese",
    "a confirmer",
    "selon interpretation",
    "pourrait egalement",
    "alternative possible",
    "classification indicative",
    "doute sur",
)

_VAGUE_DESCRIPTION_HINTS = (
    "appareil",
    "produit",
    "article",
    "marchandise",
    "electronique",
    "divers",
    "autre",
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _normalize_for_match(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _is_hs_code_missing(hs_code: str | None) -> bool:
    normalized = _normalize_for_match(str(hs_code or "").strip())
    if not normalized:
        return True
    if normalized in ("non applicable", "n/a", "na"):
        return True
    return "non renseign" in normalized


def _is_field_unset(value: str | None) -> bool:
    normalized = _normalize_for_match(str(value or "").strip())
    return not normalized or "non renseign" in normalized


def _description_quality_signals(description: str) -> tuple[bool, bool]:
    """Retourne (trop_courte, trop_vague) a partir de la description marchandise."""
    normalized = _normalize_for_match(description)
    words = [word for word in re.split(r"\s+", normalized.strip()) if len(word) >= 3]
    is_short = len(normalized.strip()) < 30 or len(words) < 4
    is_vague = len(words) <= 6 and any(hint in normalized for hint in _VAGUE_DESCRIPTION_HINTS)
    return is_short, is_vague


def assess_contestation_risk(item: dict[str, Any]) -> dict[str, str]:
    """
    Evalue le risque de contestation d'une classification.

    La confiance de classification (`confidence`) mesure la solidite du code SH.
    `quantity_confidence` mesure seulement la fiabilite d'extraction de quantite
    dans le texte source : elle n'indique pas si la fiche produit est incomplete.
    """
    confidence = _safe_int(item.get("confidence"), 0)
    description_quality = _safe_int(item.get("description_quality"), 0)
    classification_status = str(item.get("classification_status") or "").strip().lower()
    missing_fields = item.get("missing_fields") if isinstance(item.get("missing_fields"), list) else []
    hs_code = str(item.get("hs_code") or "")
    description = str(item.get("description") or "")
    justification = _normalize_for_match(str(item.get("justification") or ""))
    has_position_label = bool(str(item.get("position_label") or "").strip())
    is_short, is_vague = _description_quality_signals(description)

    if _is_hs_code_missing(hs_code):
        return {"risk_level": "high", "risk_label": "Classement incertain."}

    if classification_status == "provisoire" or item.get("subposition_status") == "a_determiner":
        missing = item.get("missing_fields") if isinstance(item.get("missing_fields"), list) else []
        if missing:
            first = str(missing[0]).strip()
            if first:
                return {
                    "risk_level": "medium",
                    "risk_label": f"Information insuffisante : {first[:140]}.",
                }
        return {
            "risk_level": "medium",
            "risk_label": "Information insuffisante pour classer avec certitude.",
        }

    if missing_fields:
        critical_missing = any(
            "surface exterieure" in _normalize_for_match(str(field))
            for field in missing_fields
        )
        if critical_missing:
            return {
                "risk_level": "medium",
                "risk_label": "Information insuffisante pour classer avec certitude.",
            }

    has_uncertainty = any(keyword in justification for keyword in _UNCERTAINTY_KEYWORDS)
    if confidence < 55 or (confidence < 70 and has_uncertainty):
        return {"risk_level": "high", "risk_label": "Classement incertain."}

    if not has_position_label and confidence < 75:
        return {"risk_level": "high", "risk_label": "Classement incertain."}

    # Classement solide + libelle TEC + fiche/description exploitable => faible risque.
    if (
        confidence >= 85
        and has_position_label
        and not is_short
        and not is_vague
        and not has_uncertainty
    ):
        return {"risk_level": "low", "risk_label": "Faible risque de contestation."}

    if (
        confidence >= 80
        and description_quality >= 85
        and has_position_label
        and not has_uncertainty
    ):
        return {"risk_level": "low", "risk_label": "Faible risque de contestation."}

    incomplete_score = 0
    if is_short:
        incomplete_score += 2
    if is_vague:
        incomplete_score += 2
    if confidence < 70:
        incomplete_score += 2
    elif confidence < 80:
        incomplete_score += 1
    if _is_field_unset(item.get("origin")) and _is_field_unset(item.get("value")) and is_short:
        incomplete_score += 1

    if incomplete_score >= 2:
        return {"risk_level": "medium", "risk_label": "Description incomplète."}

    return {"risk_level": "low", "risk_label": "Faible risque de contestation."}


def enrich_classifications_with_risk(classifications: list[Any]) -> None:
    for item in classifications:
        if not isinstance(item, dict):
            continue
        risk = assess_contestation_risk(item)
        item["risk_level"] = risk["risk_level"]
        item["risk_label"] = risk["risk_label"]
