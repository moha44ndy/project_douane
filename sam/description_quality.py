"""Score de richesse de la fiche produit (distinct de la fiabilite quantite)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_PRODUCT_HEADER = re.compile(
    r"^(?:produit|marchandise|article|designation)\s*:\s*.+",
    re.IGNORECASE | re.UNICODE,
)
_DOSSIER_KEYWORDS = ("composition", "caracteristique", "specification", "usage", "capacite")


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _is_field_set(value: str | None) -> bool:
    normalized = _normalize(str(value or "").strip())
    return bool(normalized) and "non renseign" not in normalized


def is_structured_dossier_text(text: str) -> bool:
    raw = (text or "").replace("\r", "\n").strip()
    if not raw:
        return False
    first_line = ""
    for line in raw.splitlines():
        if line.strip():
            first_line = line.strip()
            break
    if not first_line or not _PRODUCT_HEADER.match(first_line):
        return False
    ascii_norm = _normalize(raw)
    return any(keyword in ascii_norm for keyword in _DOSSIER_KEYWORDS)


def assess_description_quality(
    *,
    source_text: str | None = None,
    description: str | None = None,
    origin: str | None = None,
    value: str | None = None,
    position_label: str | None = None,
    justification: str | None = None,
) -> int:
    """
    Evalue la richesse de la fiche produit (0-100).

    Ce score est independant de `quantity_confidence`, qui mesure seulement
    la fiabilite d'extraction de la quantite dans le texte source.
    """
    if source_text and is_structured_dossier_text(source_text):
        score = 75
        norm = _normalize(source_text)
        if "composition" in norm:
            score += 8
        if "caracteristique" in norm or "specification" in norm:
            score += 8
        if "usage" in norm:
            score += 4
        if "capacite" in norm or "dimension" in norm:
            score += 4
        if re.search(r"\b(?:origine|provenant)\b", norm):
            score += 4
        if re.search(r"\b(?:valeur|prix|dollars?|usd|eur|fcfa)\b", norm):
            score += 4
        return min(95, score)

    score = 35
    desc = _normalize(str(description or ""))
    words = [word for word in re.split(r"\s+", desc.strip()) if len(word) >= 2]
    if len(words) >= 12:
        score += 30
    elif len(words) >= 7:
        score += 20
    elif len(words) >= 4:
        score += 10

    if _is_field_set(origin):
        score += 10
    if _is_field_set(value):
        score += 10
    if str(position_label or "").strip():
        score += 8
    if len(str(justification or "").strip()) >= 80:
        score += 7

    return max(0, min(100, score))


def enrich_item_description_quality(item: dict[str, Any], source_text: str | None = None) -> None:
    if item.get("description_quality") is not None:
        return
    item["description_quality"] = assess_description_quality(
        source_text=source_text,
        description=str(item.get("description") or ""),
        origin=str(item.get("origin") or ""),
        value=str(item.get("value") or ""),
        position_label=str(item.get("position_label") or ""),
        justification=str(item.get("justification") or ""),
    )
