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
_POSITION_LABEL_INDEX: dict[str, str] | None = None
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


_SUBPOS_CODE_RE = re.compile(r"\d{4}\.\d{2}")


def _extract_position_headings_from_chunk(text: str) -> dict[str, str]:
    """Extract position headings (XX.XX format) from a TEC chunk.

    TEC format example:
        85.04  Transformateurs électriques, convertisseurs élec-
        triques statiques (redresseurs, par exemple), bobines
        de réactance et selfs.
         8504.10.00.00 - Ballasts pour lampes ou tubes ...

    Strategy: find XX.XX codes, capture everything after them until the
    first XXXX.XX sub-position code appears (signaling the heading is over).
    """
    results: dict[str, str] = {}
    pos_pattern = re.compile(r"(?:^|\n)\s*(\d{2}\.\d{2})\s{2,}")

    for match in pos_pattern.finditer(text):
        pos_code = match.group(1)
        digits = pos_code.replace(".", "")
        if len(digits) != 4:
            continue

        start = match.end()
        remaining = text[start:]

        subpos_match = _SUBPOS_CODE_RE.search(remaining)
        if subpos_match:
            heading_text = remaining[: subpos_match.start()]
        else:
            heading_text = remaining[:300]

        heading_text = re.sub(r"-\s*\n\s*", "", heading_text)
        heading_text = re.sub(r"\s+", " ", heading_text).strip()
        heading_text = heading_text.rstrip(".")
        heading_text = re.sub(r"\s*[uU]\s+\d+\s+\d\s*$", "", heading_text).strip()

        if len(heading_text) >= 10:
            prev = results.get(digits, "")
            if len(heading_text) > len(prev):
                results[digits] = heading_text

    return results


def build_position_label_index(
    full_index: dict[str, str],
    chunks: Iterable | None = None,
) -> dict[str, str]:
    """Build a 4-digit position → label index.

    Strategy:
    1. Scan TEC chunks for position headings (XX.XX format) — these are
       the authoritative position titles (e.g. "85.04 Transformateurs
       électriques, convertisseurs électriques statiques...").
    2. Fall back to the longest sub-position label for positions not
       found in step 1.
    """
    result: dict[str, str] = {}

    if chunks is not None:
        for chunk in chunks:
            text = chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
            for pos_key, heading in _extract_position_headings_from_chunk(text).items():
                prev = result.get(pos_key, "")
                if len(heading) > len(prev):
                    result[pos_key] = heading

    pos_labels: dict[str, list[str]] = {}
    for code, label in full_index.items():
        digits = re.sub(r"\D", "", code)
        if len(digits) >= 4:
            pos_key = digits[:4]
            if pos_key not in result:
                pos_labels.setdefault(pos_key, []).append(label)
    for pos_key, labels in pos_labels.items():
        labels.sort(key=len, reverse=True)
        result[pos_key] = labels[0]

    return result


def set_tariff_label_index(
    index: dict[str, str],
    chunks: Iterable | None = None,
) -> None:
    global _TARIFF_LABEL_INDEX, _POSITION_LABEL_INDEX
    _TARIFF_LABEL_INDEX = index
    _POSITION_LABEL_INDEX = build_position_label_index(index, chunks=chunks)


def get_tariff_label_index() -> dict[str, str]:
    return _TARIFF_LABEL_INDEX or {}


def get_position_label_index() -> dict[str, str]:
    return _POSITION_LABEL_INDEX or {}


def _normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip accents, remove punctuation."""
    import unicodedata
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _compute_term_overlap(query_terms: set[str], heading_text: str) -> float:
    """Score = ratio of query terms found in the heading text."""
    if not query_terms:
        return 0.0
    heading_normalized = _normalize_text(heading_text)
    heading_words = set(heading_normalized.split())
    matches = 0
    for term in query_terms:
        if term in heading_words or any(term in hw for hw in heading_words):
            matches += 1
    return matches / len(query_terms)


def find_positions_by_heading_match(
    product_description: str,
    *,
    product_type: str = "",
    function_usage: str = "",
    family: str = "",
    top_n: int = 3,
    min_score: float = 0.25,
) -> list[tuple[str, str, float]]:
    """Find position codes whose heading text matches the product description.

    Returns list of (position_code_XX.XX, heading_label, score) sorted by score.
    """
    pos_idx = get_position_label_index()
    if not pos_idx:
        return []

    search_text = " ".join(filter(None, [product_description, product_type, function_usage, family]))
    query_terms = set(_normalize_text(search_text).split())
    # Remove very common/short words
    stopwords = {"de", "du", "des", "le", "la", "les", "un", "une", "et", "ou", "en",
                 "pour", "par", "avec", "dans", "sur", "a", "au", "aux", "d", "l",
                 "qui", "que", "ce", "ces", "son", "sa", "ses", "ne", "pas", "est",
                 "sont", "etre", "avoir", "fait", "faire", "plus", "moins", "tres",
                 "autre", "autres", "non", "y", "n"}
    query_terms = {t for t in query_terms if len(t) >= 3 and t not in stopwords}
    if not query_terms:
        return []

    scored: list[tuple[str, str, float]] = []
    for pos_key, heading in pos_idx.items():
        score = _compute_term_overlap(query_terms, heading)
        if score >= min_score:
            pos_code = f"{pos_key[:2]}.{pos_key[2:]}"
            scored.append((pos_code, heading, score))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:top_n]


def find_positions_by_label_keywords(
    keywords: list[str],
    *,
    min_matches: int = 1,
    top_n: int = 3,
) -> list[tuple[str, str, float]]:
    """Find positions whose TEC heading contains industrial/customs keywords."""
    pos_idx = get_position_label_index()
    if not pos_idx or not keywords:
        return []

    normalized_keywords = [_normalize_text(k) for k in keywords if k.strip()]
    normalized_keywords = [k for k in normalized_keywords if len(k) >= 3]
    if not normalized_keywords:
        return []

    scored: list[tuple[str, str, float]] = []
    for pos_key, heading in pos_idx.items():
        norm_heading = _normalize_text(heading)
        matches = sum(1 for kw in normalized_keywords if kw in norm_heading)
        if matches >= min_matches:
            pos_code = f"{pos_key[:2]}.{pos_key[2:]}"
            score = matches / len(normalized_keywords)
            scored.append((pos_code, heading, score))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:top_n]


def list_subpositions_for_position(position_code: str) -> list[tuple[str, str]]:
    """Return all sub-position codes and labels under a 4-digit position.

    Args:
        position_code: position in XX.XX or XXXX format
    Returns:
        Sorted list of (code, label) tuples
    """
    digits = re.sub(r"\D", "", (position_code or "").strip())
    if len(digits) < 4:
        return []
    prefix = digits[:4]
    idx = get_tariff_label_index()
    results = []
    for code, label in idx.items():
        code_digits = re.sub(r"\D", "", code)
        if code_digits.startswith(prefix):
            results.append((code, label))
    results.sort(key=lambda x: x[0])
    return results


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

    # For position codes XX.XX (e.g. 85.17), prioritize position-level headings
    parts = [p for p in normalized.split(".") if p.isdigit()]
    if len(parts) == 2 and len(parts[0] + parts[1]) == 4 and _POSITION_LABEL_INDEX:
        pos_label = _POSITION_LABEL_INDEX.get(parts[0] + parts[1])
        if pos_label:
            return pos_label

    lookup_index = index if index is not None else get_tariff_label_index()
    if not lookup_index:
        return None

    for candidate in _hs_lookup_candidates(normalized):
        label = lookup_index.get(candidate)
        if label:
            return label

    return None
