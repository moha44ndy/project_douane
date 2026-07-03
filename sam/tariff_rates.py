"""Lookup D.D., R.S. et U.S. depuis les tableaux TEC (chunks)."""

from __future__ import annotations

import re
from typing import Any, Iterable

from .tariff_labels import _hs_lookup_candidates

_TARIFF_CODE_PREFIX_RE = re.compile(
    r"^(\d{4}\.\d{2}(?:\.\d{2}(?:\.\d{2})?)?)\s*(?:-{1,3}\s*)?",
)
_TARIFF_RATE_TAIL_RE = re.compile(
    r"\s+(?P<unit>kg|u|l)\s+(?P<dd>\d+)\s+(?P<rs>\d+)\s*$",
    re.IGNORECASE,
)

_US_UNIT_LABELS: dict[str, str] = {
    "u": "PCE",
    "kg": "KG",
    "l": "L",
}

OTHER_TAXES_OUT_OF_TEC = "Selon le pays d'importation (hors TEC)"
PROVISIONAL_TAX_VALUE = "A confirmer"
PROVISIONAL_US_VALUE = "A determiner apres validation de la sous-position"
PROVISIONAL_TAXES_NOTE = "Taux indicatifs sous reserve de la sous-position definitive"

_TARIFF_RATE_INDEX: dict[str, dict[str, str]] | None = None


def build_tariff_rate_index(chunks: Iterable) -> dict[str, dict[str, str]]:
    """Construit un index code SH -> {us_unit, dd_rate, rs_rate} depuis les chunks TEC."""
    index: dict[str, dict[str, str]] = {}
    for chunk in chunks:
        text = chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            code_match = _TARIFF_CODE_PREFIX_RE.match(line)
            if not code_match:
                continue
            tail_match = _TARIFF_RATE_TAIL_RE.search(line)
            if not tail_match:
                continue
            code = code_match.group(1)
            index[code] = {
                "us_unit": tail_match.group("unit").lower(),
                "dd_rate": tail_match.group("dd"),
                "rs_rate": tail_match.group("rs"),
            }
    return index


def set_tariff_rate_index(index: dict[str, dict[str, str]]) -> None:
    global _TARIFF_RATE_INDEX
    _TARIFF_RATE_INDEX = index


def get_tariff_rate_index() -> dict[str, dict[str, str]]:
    return _TARIFF_RATE_INDEX or {}


def format_us_unit(unit_code: str | None) -> str:
    if not unit_code:
        return "N/R"
    normalized = str(unit_code).strip().lower()
    return _US_UNIT_LABELS.get(normalized, normalized.upper())


def lookup_tariff_rates(
    hs_code: str | None,
    index: dict[str, dict[str, str]] | None = None,
) -> dict[str, str] | None:
    """Retourne les taux TEC pour un code SH, ou None si introuvable."""
    if not hs_code:
        return None
    normalized = str(hs_code).strip()
    if not normalized or normalized.upper() in (
        "NON APPLICABLE",
        "NON RENSEIGNE",
        "NON RENSEIGNÉ",
        "N/A",
        "NA",
    ):
        return None

    lookup_index = index if index is not None else get_tariff_rate_index()
    if not lookup_index:
        return None

    for candidate in _hs_lookup_candidates(normalized):
        rates = lookup_index.get(candidate)
        if rates:
            return dict(rates)
    return None


def _hs_digit_count(hs_code: str | None) -> int:
    return len(re.sub(r"\D", "", str(hs_code or "")))


def _requires_provisional_taxes(item: dict[str, Any]) -> bool:
    if item.get("subposition_status") == "a_determiner":
        return True
    if str(item.get("classification_status") or "").strip().lower() == "provisoire":
        return True
    if _hs_digit_count(item.get("hs_code")) < 8:
        return True
    return False


def _confirmed_lookup_code(item: dict[str, Any]) -> str:
    hs_code = str(item.get("hs_code") or "").strip()
    if _hs_digit_count(hs_code) >= 8:
        return hs_code
    return ""


def _apply_provisional_tax_placeholders(item: dict[str, Any]) -> None:
    item["dd_rate"] = PROVISIONAL_TAX_VALUE
    item["rs_rate"] = PROVISIONAL_TAX_VALUE
    item["us_unit"] = PROVISIONAL_US_VALUE
    item["other_taxes"] = OTHER_TAXES_OUT_OF_TEC
    item["other_taxes_source"] = "national"
    item["taxes_source"] = "provisional"
    item["taxes_note"] = PROVISIONAL_TAXES_NOTE


def enrich_item_tariff_rates(item: dict[str, Any], index: dict[str, dict[str, str]] | None = None) -> None:
    """Ecrase les taux LLM par les valeurs TEC quand la sous-position est confirmee."""
    lookup_index = index if index is not None else get_tariff_rate_index()

    if _requires_provisional_taxes(item):
        _apply_provisional_tax_placeholders(item)
        return

    lookup_code = _confirmed_lookup_code(item)
    rates = lookup_tariff_rates(lookup_code, lookup_index) if lookup_code else None

    if rates:
        item["dd_rate"] = f"{rates['dd_rate']} %"
        item["rs_rate"] = f"{rates['rs_rate']} %"
        item["us_unit"] = format_us_unit(rates["us_unit"])
        item["taxes_source"] = "tec"
        item.pop("taxes_note", None)
    else:
        item.setdefault("dd_rate", "N/R")
        item.setdefault("rs_rate", "N/R")
        item.setdefault("us_unit", "N/R")
        item["taxes_source"] = "unavailable"

    item["other_taxes"] = OTHER_TAXES_OUT_OF_TEC
    item["other_taxes_source"] = "national"
