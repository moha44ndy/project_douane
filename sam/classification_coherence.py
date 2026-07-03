"""Aligne code SH, justification, confiance, droits et risque sur un meme niveau de precision."""

from __future__ import annotations

import re
from typing import Any

from .tariff_position_rules import position_code_from_hs

_HS_CODE_RE = re.compile(r"\b(\d{4}\.\d{2}(?:\.\d{2}(?:\.\d{2})?)?)\b")
_INSUFFICIENT_SUBPOSITION_RE = re.compile(
    r"Information insuffisante pour determiner avec certitude la sous-position[^.!?]*[.!?]?",
    re.IGNORECASE,
)
_CONFIRMED_CRITERIA_NOTE = (
    "Sous-position confirmee : les criteres discriminants prevus par le TEC "
    "sont satisfaits par la description fournie."
)


def _hs_digit_count(hs_code: str | None) -> int:
    return len(re.sub(r"\D", "", str(hs_code or "")))


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _subposition_resolution(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("subposition_resolution")
    return raw if isinstance(raw, dict) else {}


def is_subposition_confirmed(item: dict[str, Any]) -> bool:
    resolution = _subposition_resolution(item)
    if resolution.get("status") == "confirmed":
        return True
    if item.get("subposition_status") == "a_determiner":
        return False
    if str(item.get("classification_status") or "").strip().lower() == "provisoire":
        return False
    return _hs_digit_count(item.get("hs_code")) >= 8


def _strip_subposition_codes_from_text(text: str, position: str) -> str:
    prefix = position.replace(".", "")

    def _replace(match: re.Match[str]) -> str:
        code = match.group(1)
        digits = re.sub(r"\D", "", code)
        if len(digits) > 4:
            return position
        return code

    cleaned = _HS_CODE_RE.sub(_replace, text or "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;.")
    return cleaned


def _ensure_provisional_justification(item: dict[str, Any], position: str) -> None:
    justification = str(item.get("justification") or "").strip()
    justification = _strip_subposition_codes_from_text(justification, position)

    missing = item.get("missing_fields") or []
    if isinstance(missing, list):
        critical = [str(field) for field in missing if str(field).strip()]
    else:
        critical = []

    resolution = _subposition_resolution(item)
    for field in resolution.get("missing_criteria") or []:
        if str(field).strip() and str(field) not in critical:
            critical.append(str(field))

    if critical:
        note = (
            "Information insuffisante pour determiner avec certitude la sous-position : "
            + "; ".join(critical[:3])
        )
        if note.lower() not in justification.lower():
            justification = f"{justification} {note}".strip() if justification else note

    item["justification"] = justification.strip()


def _ensure_confirmed_justification(item: dict[str, Any], resolution: dict[str, Any]) -> None:
    justification = str(item.get("justification") or "").strip()
    justification = _INSUFFICIENT_SUBPOSITION_RE.sub("", justification).strip()
    justification = re.sub(r"\s{2,}", " ", justification).strip()

    matched = str(resolution.get("matched_code") or item.get("hs_code") or "").strip()
    if matched and matched not in justification:
        note = f"{_CONFIRMED_CRITERIA_NOTE} Code retenu : {matched}."
    else:
        note = _CONFIRMED_CRITERIA_NOTE

    if note.lower() not in justification.lower():
        justification = f"{justification} {note}".strip() if justification else note
    item["justification"] = justification


def enforce_classification_coherence(item: dict[str, Any]) -> None:
    """
    Garantit la coherence entre le niveau de precision affiche, la justification,
    la confiance et les metadonnees derivees (droits, risque).
    """
    if not isinstance(item, dict):
        return

    resolution = _subposition_resolution(item)
    if resolution:
        confirmed = resolution.get("status") == "confirmed"
    else:
        confirmed = (
            not item.get("subposition_status")
            and str(item.get("classification_status") or "").strip().lower() == "confirmee"
            and _hs_digit_count(item.get("hs_code")) >= 8
        )
    position = position_code_from_hs(str(item.get("hs_code") or ""))
    digits = _hs_digit_count(item.get("hs_code"))

    if not confirmed:
        justified = str(
            resolution.get("hs_code") or resolution.get("heading_code") or position
        ).strip()
        justified_digits = _hs_digit_count(justified)
        if digits > justified_digits and justified_digits >= 4:
            item.setdefault("hs_code_suggested", str(item.get("hs_code") or "").strip())
            item["hs_code"] = justified
            digits = justified_digits

        item["subposition_status"] = "a_determiner"
        item["classification_status"] = "provisoire"

        cap = _safe_int(resolution.get("confidence_cap"), 65)
        item["confidence"] = min(_safe_int(item.get("confidence"), 90), cap)
        return

    item.pop("subposition_status", None)
    item.pop("subposition_label", None)
    item["classification_status"] = "confirmee"

    cap = _safe_int(resolution.get("confidence_cap"), 85)
    current = _safe_int(item.get("confidence"), 0)
    item["confidence"] = min(max(current, cap), 95)
