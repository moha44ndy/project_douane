"""Lookup des libelles officiels TEC a partir des chunks tarifaires."""

from __future__ import annotations

import re
from typing import Iterable

_TARIFF_LABEL_RE = re.compile(
    r"(\d{4}\.\d{2}(?:\.\d{2}(?:\.\d{2})?)?)\s*(?:-{2,}|-)\s*"
    r"((?:[^\n]+(?:\n\s+[^\n\d][^\n]*)?))",
    re.MULTILINE,
)
_TARIFF_COLUMNS_RE = re.compile(
    r"\s+(?:kg|u|l|m[²2³3]|m³)\s+\d.*$",
    re.IGNORECASE,
)
_TARIFF_RATE_COLUMNS_RE = re.compile(r"\s+\d+\s+\d\s*$")

_TARIFF_LABEL_INDEX: dict[str, str] | None = None


def _clean_label_fragment(raw: str) -> str:
    label = re.sub(r"\s+", " ", raw).strip()
    label = re.sub(r"^-\s*", "", label)
    label = _TARIFF_COLUMNS_RE.sub("", label).strip()
    label = _TARIFF_RATE_COLUMNS_RE.sub("", label).strip()
    return label


def build_tariff_label_index(chunks: Iterable) -> dict[str, str]:
    """Construit un index code SH -> libelle officiel depuis les chunks TEC."""
    index: dict[str, str] = {}
    for chunk in chunks:
        text = chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
        for match in _TARIFF_LABEL_RE.finditer(text):
            code = match.group(1)
            label = _clean_label_fragment(match.group(2))
            if not label:
                continue
            previous = index.get(code)
            if not previous or len(label) > len(previous):
                index[code] = label
    return index


def set_tariff_label_index(index: dict[str, str]) -> None:
    global _TARIFF_LABEL_INDEX
    _TARIFF_LABEL_INDEX = index


def get_tariff_label_index() -> dict[str, str]:
    return _TARIFF_LABEL_INDEX or {}


def _hs_lookup_candidates(hs_code: str) -> list[str]:
    parts = [part for part in hs_code.strip().split(".") if part.isdigit()]
    if len(parts) < 2:
        return []

    candidates: list[str] = []
    if len(parts) >= 4:
        candidates.append(".".join(parts[:4]))
    if len(parts) == 3:
        candidates.append(".".join(parts + ["00"]))
        candidates.append(".".join(parts))
    if len(parts) == 2:
        candidates.append(".".join(parts + ["00", "00"]))
        candidates.append(".".join(parts))

    for size in range(min(4, len(parts)), 1, -1):
        candidates.append(".".join(parts[:size]))

    return list(dict.fromkeys(candidates))


def lookup_position_label(
    hs_code: str | None,
    index: dict[str, str] | None = None,
) -> str | None:
    """Retourne le libelle TEC pour un code SH, ou None si introuvable."""
    if not hs_code:
        return None

    normalized = str(hs_code).strip()
    if not normalized:
        return None
    if normalized.upper() in ("NON APPLICABLE", "NON RENSEIGNE", "NON RENSEIGNÉ", "N/A", "NA"):
        return None

    lookup_index = index if index is not None else get_tariff_label_index()
    if not lookup_index:
        return None

    for candidate in _hs_lookup_candidates(normalized):
        label = lookup_index.get(candidate)
        if label:
            return label
    return None
