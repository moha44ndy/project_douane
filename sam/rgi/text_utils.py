from __future__ import annotations

import re
import unicodedata

_ASSORTMENT_HINTS = (
    "assortiment",
    "coffret",
    "kit ",
    " kit",
    "trousse",
    "ensemble",
    "vendu ensemble",
    "presente ensemble",
    "presente comme",
    "lot cadeau",
    "pack cadeau",
    "comprenant",
    "contient",
    "inclut",
)

_INTEGRATED_HINTS = (
    "multifonction",
    "multi-fonction",
    "combine",
    "combinant",
    "tout en un",
    "tout-en-un",
    "3 en 1",
    "4 en 1",
)

_RGI2A_HINTS = (
    "demonte",
    "demonté",
    "non monte",
    "non monté",
    "incomplet",
    "non fini",
    "ckd",
    "skd",
    "montage industriel",
)

_CONTAINER_LABEL_HINTS = (
    "emballage",
    "etui",
    "boite",
    "coffret",
    "contenant",
    "emballages",
)


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def chapter_from_hs(hs_code: str | None) -> str:
    code = re.sub(r"\D", "", str(hs_code or ""))
    return code[:2] if len(code) >= 2 else ""


def position_from_hs(hs_code: str | None) -> str:
    parts = [p for p in str(hs_code or "").split(".") if p.isdigit()]
    if len(parts) < 2:
        return ""
    return f"{parts[0]}.{parts[1]}"


def hs_digit_count(hs_code: str | None) -> int:
    return len(re.sub(r"\D", "", str(hs_code or "")))


def has_material_composition_pattern(text: str) -> bool:
    return bool(re.search(r"\d+(?:[.,]\d+)?\s*%\s*\w+", normalize(text)))


def mentions_assortment(text: str) -> bool:
    norm = normalize(text)
    return any(hint in norm for hint in _ASSORTMENT_HINTS)


def mentions_integrated_product(text: str) -> bool:
    norm = normalize(text)
    return any(hint in norm for hint in _INTEGRATED_HINTS)


def mentions_rgi2a_product(text: str) -> bool:
    norm = normalize(text)
    return any(hint in norm for hint in _RGI2A_HINTS)


def listed_component_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in (text or "").replace("\r", "\n").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if re.match(r"^[-*•]\s+", stripped) or re.match(r"^\d+[\.)]\s+", stripped):
            content = re.sub(r"^[-*•\d\)\.]+\s*", "", stripped).strip()
            if len(content) >= 3:
                lines.append(content)
    return lines


def split_user_queries_safe(source_text: str) -> list[str]:
    try:
        from ..rag import split_user_queries

        return split_user_queries(source_text) or []
    except Exception:
        text = (source_text or "").strip()
        return [text] if text else []


def count_distinct_user_products(source_text: str) -> int:
    """Un coffret/kit avec liste de composants = une seule unite commerciale."""
    if mentions_assortment(source_text):
        return 1
    if listed_component_lines(source_text) and re.search(
        r"\b(?:comprenant|contient|inclut|avec)\b", normalize(source_text)
    ):
        return 1
    queries = split_user_queries_safe(source_text)
    return len(queries) if queries else 1


def label_looks_like_container(label: str) -> bool:
    norm = normalize(label)
    return any(hint in norm for hint in _CONTAINER_LABEL_HINTS)


def distinct_positions(items: list[dict]) -> set[str]:
    positions: set[str] = set()
    for item in items:
        pos = position_from_hs(item.get("hs_code"))
        if pos:
            positions.add(pos)
        else:
            ch = str(item.get("chapter") or chapter_from_hs(item.get("hs_code")) or "").strip()
            if ch:
                positions.add(f"ch{ch}")
    return positions


def chapter_specific_rule_blocks(item: dict, source_text: str | None = None) -> bool:
    """
    True seulement si une classification provisoire anterieure reste justifiee
    par la description courante. Ne jamais bloquer une nouvelle analyse uniquement
    parce qu'un autre cas exigeait auparavant une information supplementaire.
    """
    source = (source_text or str(item.get("source_query") or item.get("description") or "")).strip()
    had_provisional_state = (
        str(item.get("subposition_status") or "") == "a_determiner"
        or bool(item.get("requires_exterior_surface"))
        or str(item.get("classification_status") or "").lower() == "provisoire"
    )
    if not source:
        return had_provisional_state

    from ..classification_completeness import analyze_classification_completeness
    from ..tariff_subposition import resolve_subposition_from_tec

    probe_item = dict(item)
    for key in (
        "subposition_status",
        "subposition_label",
        "subposition_resolution",
        "requires_exterior_surface",
        "subposition_detail_required",
    ):
        probe_item.pop(key, None)

    analysis = analyze_classification_completeness(source_text=source, item=probe_item)
    still_missing = bool(analysis.get("missing_critical"))

    if not still_missing:
        hs = str(probe_item.get("hs_code") or item.get("hs_code") or "").strip()
        suggested = str(item.get("hs_code_suggested") or "").strip()
        hs_digits = len(re.sub(r"\D", "", hs))
        suggested_digits = len(re.sub(r"\D", "", suggested))
        if suggested_digits > hs_digits:
            hs = suggested

        if hs:
            subdivision = resolve_subposition_from_tec(hs, source)
            if subdivision.status == "confirmed":
                return False
            still_missing = bool(subdivision.missing_criteria)

    if not still_missing:
        return False

    return had_provisional_state
