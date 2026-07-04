"""Validation de la position (4 chiffres) à l'intérieur du chapitre.

Compare le libellé TEC de la position retenue avec la description enrichie
du produit (issue de l'identification internet). Si une autre position dans
le même chapitre a un libellé TEC nettement plus compatible, corrige.

Aucune table hardcodée : tout repose sur l'index TEC chargé au démarrage
et sur la description enrichie par la recherche internet.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

from .tariff_labels import get_tariff_label_index, lookup_position_label
from .tariff_metadata import get_position_heading
from .tariff_position_rules import position_code_from_hs

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _extract_chapter(hs_code: str) -> str:
    digits = re.sub(r"\D", "", hs_code or "")
    return digits[:2] if len(digits) >= 2 else ""


def _position_label(position_code: str) -> str:
    """Récupère le libellé officiel TEC d'une position."""
    label = lookup_position_label(position_code)
    if label:
        return label
    heading = get_position_heading(position_code)
    return heading or ""


def _get_chapter_positions(chapter: str) -> dict[str, str]:
    """Retourne toutes les positions (XX.XX) d'un chapitre depuis l'index TEC."""
    index = get_tariff_label_index()
    if not index:
        return {}
    positions: dict[str, str] = {}
    prefix = chapter.zfill(2)
    for code, label in index.items():
        code_digits = re.sub(r"\D", "", code)
        if len(code_digits) >= 4 and code_digits[:2] == prefix:
            pos = f"{code_digits[:2]}.{code_digits[2:4]}"
            if pos not in positions:
                positions[pos] = label
    return positions


def _keyword_match_score(product_desc: str, tec_label: str) -> float:
    """Score de pertinence entre la description produit et un libellé TEC.

    Purement lexical : compte le ratio de mots significatifs du libellé TEC
    présents dans la description produit. Pas de bonus hardcodé.
    """
    desc_norm = _normalize(product_desc)
    label_norm = _normalize(tec_label)

    if not desc_norm or not label_norm:
        return 0.0

    stopwords = {
        "autres", "autre", "parties", "partie", "non", "compris",
        "ailleurs", "denommes", "des", "les", "pour", "avec",
        "sans", "dans", "une", "qui", "sont", "ces", "dont",
    }
    label_keywords = set(re.findall(r"[a-z]{3,}", label_norm)) - stopwords
    if not label_keywords:
        return 0.0

    hits = sum(1 for kw in label_keywords if kw in desc_norm)
    return hits / len(label_keywords)


def find_better_position_in_chapter(
    hs_code: str,
    product_description: str,
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """
    Explore TOUTES les positions du chapitre dans l'index TEC et compare
    leurs libellés officiels avec la description enrichie du produit.
    Retourne un dict si une meilleure position existe, None sinon.
    """
    if not hs_code or not product_description:
        return None

    current_position = position_code_from_hs(hs_code)
    chapter = _extract_chapter(hs_code)
    if not chapter or not current_position:
        return None

    current_label = _position_label(current_position)
    current_score = _keyword_match_score(product_description, current_label)

    if not current_label:
        logger.debug(
            "[position_validator] no TEC label for %s, skipping correction",
            current_position,
        )
        return None

    rival_positions: dict[str, float] = {}
    rival_labels: dict[str, str] = {}

    chapter_positions = _get_chapter_positions(chapter)
    for pos, label in chapter_positions.items():
        if pos == current_position or not label:
            continue
        score = _keyword_match_score(product_description, label)
        if score > 0:
            rival_positions[pos] = score
            rival_labels[pos] = label

    if candidates:
        for entry in candidates:
            pos = str(entry.get("position_code") or "").strip()
            if not pos or pos == current_position:
                continue
            if _extract_chapter(pos.replace(".", "")) != chapter:
                continue
            if pos in rival_positions:
                continue
            label = str(entry.get("label") or "").strip() or _position_label(pos)
            if not label:
                continue
            score = _keyword_match_score(product_description, label)
            if score > 0:
                rival_positions[pos] = score
                rival_labels[pos] = label

    if not rival_positions:
        return None

    best_rival = max(rival_positions, key=lambda k: rival_positions[k])
    best_score = rival_positions[best_rival]

    margin = best_score - current_score
    if margin < 0.15:
        return None

    return {
        "current_position": current_position,
        "current_label": current_label,
        "current_score": round(current_score, 3),
        "better_position": best_rival,
        "better_label": rival_labels[best_rival],
        "better_score": round(best_score, 3),
        "margin": round(margin, 3),
    }


def _build_description(
    item: dict[str, Any],
    product_identification: dict[str, Any] | None,
) -> str:
    """Construit la description fonctionnelle du produit pour le scoring.

    Priorité aux champs *fonctionnels* (product_type, function_usage)
    plutôt qu'à enriched_description qui contient souvent la composition
    physique (verre, plastique, métal…) et fausse le scoring lexical.
    """
    if isinstance(product_identification, dict) and not product_identification.get("skipped"):
        ptype = str(product_identification.get("product_type") or "").strip()
        fusage = str(product_identification.get("function_usage") or "").strip()
        pname = str(product_identification.get("product_name") or "").strip()

        functional = " ".join(filter(None, [ptype, fusage, pname]))
        if functional:
            return functional

    return str(item.get("source_query") or item.get("description") or "").strip()


def apply_position_validation(
    item: dict[str, Any],
    product_identification: dict[str, Any] | None = None,
    candidates: list[dict[str, Any]] | None = None,
) -> bool:
    """
    Compare les libellés TEC de toutes les positions du chapitre avec la
    description enrichie du produit. Si une position a un score nettement
    supérieur à celle choisie par le LLM, corrige.

    Retourne True si correction appliquée.
    """
    if not isinstance(item, dict):
        return False

    hs_code = str(item.get("hs_code") or "").strip()
    if not hs_code:
        return False

    description = _build_description(item, product_identification)
    if not description:
        return False

    logger.info(
        "[position_validator] hs_code=%s, description_len=%d",
        hs_code, len(description),
    )

    better = find_better_position_in_chapter(hs_code, description, candidates)
    if not better:
        return False

    margin = better["margin"]
    better_pos = better["better_position"]
    better_label = better["better_label"]
    current_pos = better["current_position"]

    logger.info(
        "[position_validator] CORRECTION: %s -> %s (margin=%.3f)",
        current_pos, better_pos, margin,
    )

    item.setdefault("hs_code_suggested", hs_code)
    item["hs_code"] = better_pos
    item["classification_status"] = "provisoire"

    cap = 55 if margin >= 0.3 else 60
    try:
        current_conf = int(round(float(item.get("confidence") or 90)))
    except (TypeError, ValueError):
        current_conf = 90
    item["confidence"] = min(current_conf, cap)

    label = better_label or _position_label(better_pos)
    if label:
        item["position_label"] = label

    note = (
        f"Position corrigee par validation TEC : {current_pos} -> {better_pos} "
        f"({better_label[:60]}). "
        f"Le libelle TEC de {better_pos} correspond mieux a la description du produit."
    )
    item["position_validation"] = better
    justification = str(item.get("justification") or "").strip()
    if note not in justification:
        item["justification"] = f"{note} {justification}".strip()

    return True
