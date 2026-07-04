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


def _rich_description_text(item: dict[str, Any]) -> str:
    """Texte exploitable pour juger la richesse (description + identification + source)."""
    parts: list[str] = []
    seen: set[str] = set()

    def _add(text: str) -> None:
        cleaned = str(text or "").strip()
        if not cleaned:
            return
        key = _normalize_for_match(cleaned)
        if key in seen:
            return
        seen.add(key)
        parts.append(cleaned)

    _add(str(item.get("source_query") or ""))
    _add(str(item.get("description") or ""))

    product_id = item.get("product_identification")
    if isinstance(product_id, dict):
        for field in (
            "enriched_description",
            "product_name",
            "product_type",
            "function_usage",
            "original_query",
        ):
            _add(str(product_id.get(field) or ""))

    return " ".join(parts)


def _description_quality_signals(description: str) -> tuple[bool, bool]:
    """Retourne (trop_courte, trop_vague) a partir de la description marchandise."""
    normalized = _normalize_for_match(description)
    words = [word for word in re.split(r"\s+", normalized.strip()) if len(word) >= 2]

    # Trop courte : moins de 3 mots significatifs (ex. "iPhone 15" seul).
    is_short = len(words) < 3

    # Trop vague : formulation generique sans precision (marque, modele, chiffre, usage).
    has_specific = bool(re.search(r"\d", normalized)) or len(words) >= 6
    has_technical = bool(
        re.search(
            r"\b(?:mm|cm|kg|gb|mhz|ghz|v|w|kw|ports?|pouce|litre|ml|cat\d|rj45|sfp|plc)\b",
            normalized,
        )
    )
    generic_hits = sum(1 for hint in _VAGUE_DESCRIPTION_HINTS if hint in normalized)
    is_vague = (
        not has_specific
        and not has_technical
        and len(words) <= 5
        and generic_hits >= 1
    )
    return is_short, is_vague


def assess_contestation_risk(item: dict[str, Any]) -> dict[str, str]:
    """
    Evalue le risque de contestation d'une classification.

    La confiance affichee (`confidence`) peut etre min(identification, classification).
    Pour le risque de contestation du code SH, on privilegie `classification_confidence`
    quand elle est disponible.
    """
    confidence = _safe_int(item.get("confidence"), 0)
    code_confidence = _safe_int(item.get("classification_confidence"), 0) or confidence
    description_quality = _safe_int(item.get("description_quality"), 0)
    classification_status = str(item.get("classification_status") or "").strip().lower()
    missing_fields = item.get("missing_fields") if isinstance(item.get("missing_fields"), list) else []
    hs_code = str(item.get("hs_code") or "")
    description = _rich_description_text(item)
    justification = _normalize_for_match(str(item.get("justification") or ""))
    has_position_label = bool(str(item.get("position_label") or "").strip())
    is_short, is_vague = _description_quality_signals(description)

    product_id = item.get("product_identification")
    if isinstance(product_id, dict) and product_id.get("identification_unstable"):
        if code_confidence >= 70 and has_position_label and not _is_hs_code_missing(hs_code):
            return {
                "risk_level": "medium",
                "risk_label": "Identification incertaine — classification indicative.",
            }

    # Le score de richesse de fiche prime sur les heuristiques texte courtes.
    if description_quality >= 65:
        is_short = False
        is_vague = False
    elif description_quality >= 55:
        is_vague = False

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
    if code_confidence < 55 or (code_confidence < 70 and has_uncertainty):
        return {"risk_level": "high", "risk_label": "Classement incertain."}

    if not has_position_label and code_confidence < 75:
        return {"risk_level": "high", "risk_label": "Classement incertain."}

    # Classement solide + libelle TEC + fiche/description exploitable => faible risque.
    if (
        code_confidence >= 85
        and has_position_label
        and not is_short
        and not is_vague
        and not has_uncertainty
    ):
        return {"risk_level": "low", "risk_label": "Faible risque de contestation."}

    if (
        code_confidence >= 80
        and description_quality >= 65
        and has_position_label
        and not has_uncertainty
    ):
        return {"risk_level": "low", "risk_label": "Faible risque de contestation."}

    if (
        code_confidence >= 80
        and has_position_label
        and not is_short
        and not is_vague
        and not has_uncertainty
    ):
        return {"risk_level": "low", "risk_label": "Faible risque de contestation."}

    incomplete_score = 0
    if is_short:
        incomplete_score += 2
    if is_vague:
        incomplete_score += 2
    if code_confidence < 70:
        incomplete_score += 2
    elif code_confidence < 80:
        incomplete_score += 1

    if incomplete_score >= 3:
        return {"risk_level": "medium", "risk_label": "Description incomplète."}

    return {"risk_level": "low", "risk_label": "Faible risque de contestation."}


def enrich_classifications_with_risk(classifications: list[Any]) -> None:
    for item in classifications:
        if not isinstance(item, dict):
            continue
        risk = assess_contestation_risk(item)
        item["risk_level"] = risk["risk_level"]
        item["risk_label"] = risk["risk_label"]
