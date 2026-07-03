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
_HEADING_NARRATIVE_INDEX: dict[str, str] | None = None

_TARIFF_CODE_AT_LINE_START_RE = re.compile(
    r"^\s*(\d{4}\.\d{2}(?:\.\d{2}(?:\.\d{2})?)?)\s*(?:-{2,}|-)"
)


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


def _looks_like_rate_tail(text: str) -> bool:
    return bool(re.search(r"\b(?:kg|u|l|m[²2³3])\s+\d+(?:\s+\d)?\s*$", text, re.IGNORECASE))


def _is_tariff_narrative_line(line: str) -> bool:
    """Ligne descriptive TEC (titre de sous-position) avant un code tarifaire."""
    stripped = line.strip()
    if not stripped:
        return False
    if _TARIFF_CODE_AT_LINE_START_RE.match(stripped):
        return False
    if re.match(r"^\d+\s*\.-", stripped):
        return False
    if re.match(r"^Chapitre\s+\d", stripped, re.IGNORECASE):
        return False
    if re.match(r"^N°\s*de", stripped, re.IGNORECASE):
        return False
    if re.match(r"^Section\s+", stripped, re.IGNORECASE):
        return False
    if stripped.startswith("-") or stripped.startswith("—"):
        return True
    if line.startswith(" ") and not re.match(r"^\s*\d{4}\.\d{2}", line):
        return bool(re.search(r"[a-zA-ZÀ-ÿ]{4,}", stripped))
    return False


def build_heading_narrative_index(chunks: Iterable) -> dict[str, str]:
    """
    Indexe les libelles narratifs des sous-positions a 6 chiffres (texte TEC
    precedant les codes a 8/10 chiffres).
    """
    index: dict[str, str] = {}
    for chunk in chunks:
        text = chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
        pending: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            code_match = _TARIFF_CODE_AT_LINE_START_RE.match(stripped)
            if code_match:
                code = code_match.group(1)
                digits = re.sub(r"\D", "", code)
                if len(digits) >= 6:
                    heading = f"{digits[:4]}.{digits[4:6]}"
                    narrative = re.sub(r"\s+", " ", " ".join(pending)).strip()
                    narrative = re.sub(r"^[-—]+\s*", "", narrative).strip(" :")
                    if (
                        narrative
                        and len(narrative) >= 20
                        and not _looks_like_rate_tail(narrative)
                    ):
                        previous = index.get(heading, "")
                        if len(narrative) > len(previous):
                            index[heading] = narrative
                pending = []
                continue
            if _is_tariff_narrative_line(line):
                cleaned = re.sub(r"\s+", " ", stripped).strip()
                cleaned = re.sub(r"^[-—]+\s*", "", cleaned).strip()
                if cleaned and not _looks_like_rate_tail(cleaned):
                    pending.append(cleaned)
            elif stripped and re.match(r"^(Section|Chapitre)\s+", stripped, re.IGNORECASE):
                pending = []
    return index


def set_heading_narrative_index(index: dict[str, str]) -> None:
    global _HEADING_NARRATIVE_INDEX
    _HEADING_NARRATIVE_INDEX = index


def get_heading_narrative_index() -> dict[str, str]:
    return _HEADING_NARRATIVE_INDEX or {}


def lookup_heading_narrative(hs_heading: str | None) -> str | None:
    """Libelle narratif TEC d'une sous-position a 6 chiffres (ex. 8471.30)."""
    if not hs_heading:
        return None
    normalized = str(hs_heading).strip()
    digits = re.sub(r"\D", "", normalized)
    if len(digits) < 6:
        return None
    heading = f"{digits[:4]}.{digits[4:6]}"
    index = get_heading_narrative_index()
    return index.get(heading)


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


def resolve_hs_code_to_tec(
    hs_code: str | None,
    *,
    description: str = "",
    rate_index: dict[str, dict[str, str]] | None = None,
) -> str:
    """Remplace un code SH invente (ex. 8471.30.00.00) par une ligne TEC existante."""
    if not hs_code:
        return ""
    normalized = str(hs_code).strip()
    if not normalized.replace(".", "").isdigit():
        return normalized

    from .tariff_rates import get_tariff_rate_index, lookup_tariff_rates

    lookup_index = rate_index if rate_index is not None else get_tariff_rate_index()
    if not lookup_index:
        return normalized
    if lookup_tariff_rates(normalized, lookup_index):
        return normalized

    parts = [part for part in normalized.split(".") if part.isdigit()]
    if len(parts) < 3:
        return normalized

    prefixes = [".".join(parts[:2])]
    if len(parts) >= 3 and parts[2] not in ("00", "0"):
        prefixes.append(".".join(parts[:3]))

    siblings = sorted(
        {
            key
            for key in lookup_index
            for prefix in prefixes
            if key == prefix or key.startswith(f"{prefix}.")
        }
    )
    if not siblings:
        return normalized

    from .tariff_subposition import resolve_subposition_from_tec

    heading = ".".join(parts[:3]) if len(parts) >= 3 else normalized
    result = resolve_subposition_from_tec(heading, description)
    if result.status == "confirmed" and result.matched_code:
        return result.matched_code
    if result.heading_code:
        return result.heading_code
    return normalized


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
