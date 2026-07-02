"""Regles de sous-position deduites du referentiel TEC (index des libelles)."""

from __future__ import annotations

import re
import unicodedata

_SURFACE_SENSITIVE_POSITIONS: set[str] = set()


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def position_code_from_hs(hs_code: str) -> str:
    digits = re.sub(r"\D", "", hs_code or "")
    if len(digits) < 4:
        return (hs_code or "").strip()
    return f"{digits[:2]}.{digits[2:4]}"


def build_surface_sensitive_positions(label_index: dict[str, str]) -> set[str]:
    """
    Positions dont le libelle TEC mentionne la surface exterieure
    (critere de sous-position dans la nomenclature).
    """
    positions: set[str] = set()
    for code, label in label_index.items():
        if "surface exterieure" not in _normalize(label):
            continue
        pos = position_code_from_hs(code)
        if pos:
            positions.add(pos)
    return positions


def set_surface_sensitive_positions(positions: set[str]) -> None:
    global _SURFACE_SENSITIVE_POSITIONS
    _SURFACE_SENSITIVE_POSITIONS = set(positions)


def get_surface_sensitive_positions() -> set[str]:
    return set(_SURFACE_SENSITIVE_POSITIONS)


def is_subposition_sensitive_position(hs_code: str) -> bool:
    pos = position_code_from_hs(hs_code)
    if not pos:
        return False
    return pos in _SURFACE_SENSITIVE_POSITIONS
