"""Construction de la source effective pour la resolution TEC (utilisateur + identification)."""

from __future__ import annotations

from typing import Any

IDENTIFICATION_TRUST_THRESHOLD = 70


def _identification_from_item(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None
    raw = item.get("product_identification")
    return raw if isinstance(raw, dict) else None


def identification_is_trusted(item: dict[str, Any] | None) -> bool:
    identification = _identification_from_item(item)
    if not identification or identification.get("skipped"):
        return False
    try:
        confidence = int(identification.get("identification_confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0
    return confidence >= IDENTIFICATION_TRUST_THRESHOLD


def build_effective_classification_source(
    source_text: str | None,
    item: dict[str, Any] | None = None,
) -> tuple[str, bool]:
    """
    Fusionne la saisie utilisateur et, si fiable, la fiche d'identification produit.
    Retourne (texte_effectif, identification_fiable).
    """
    parts: list[str] = []
    seen: set[str] = set()

    def _append(block: str) -> None:
        cleaned = (block or "").strip()
        if not cleaned:
            return
        key = cleaned.casefold()
        if key in seen:
            return
        seen.add(key)
        parts.append(cleaned)

    _append(source_text or "")
    if item:
        _append(str(item.get("source_query") or ""))
        _append(str(item.get("description") or ""))

    trusted = identification_is_trusted(item)
    identification = _identification_from_item(item)
    if trusted and identification:
        _append(str(identification.get("enriched_description") or ""))
        _append(str(identification.get("function_usage") or ""))
        _append(str(identification.get("product_type") or ""))
        for material in identification.get("materials") or []:
            _append(str(material))
        for characteristic in identification.get("technical_characteristics") or []:
            _append(str(characteristic))

    return "\n".join(parts), trusted
