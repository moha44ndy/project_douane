"""Verrouillage des positions TEC candidates (TOP N) avant/après le LLM."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from .tariff_labels import lookup_position_label
from .tariff_metadata import get_position_heading
from .tariff_position_rules import position_code_from_hs

_TARIFF_CODE_RE = re.compile(r"\b(\d{4}\.\d{2}(?:\.\d{2}(?:\.\d{2})?)?)\b")
_DEFAULT_MAX_POSITIONS = 5
_EXCERPT_MAX_LEN = 320


@dataclass
class PositionCandidate:
    position_code: str
    label: str
    score: float
    chapter: str = ""
    excerpt: str = ""
    matched_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_code": self.position_code,
            "label": self.label,
            "score": round(self.score, 4),
            "chapter": self.chapter,
            "excerpt": self.excerpt,
            "matched_codes": self.matched_codes[:8],
        }


def extract_tariff_codes_from_text(text: str) -> list[str]:
    """Extrait les codes SH/TEC présents dans un extrait de chunk."""
    if not text:
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _TARIFF_CODE_RE.finditer(text):
        code = match.group(1)
        if code not in seen:
            seen.add(code)
            ordered.append(code)
    return ordered


def _chunk_text(chunk: Any) -> str:
    if hasattr(chunk, "page_content"):
        return str(chunk.page_content or "")
    return str(chunk or "")


def _position_label(position_code: str, matched_codes: list[str]) -> str:
    for code in sorted(matched_codes, key=len, reverse=True):
        label = lookup_position_label(code) or lookup_position_label(position_code)
        if label:
            return label
    heading = get_position_heading(position_code)
    if heading:
        return heading
    return lookup_position_label(position_code) or "Libelle TEC non indexe"


def _build_excerpt(text: str, matched_codes: list[str]) -> str:
    if not text:
        return ""
    focus = matched_codes[0] if matched_codes else ""
    if focus:
        idx = text.find(focus)
        if idx >= 0:
            start = max(0, idx - 80)
            end = min(len(text), idx + len(focus) + _EXCERPT_MAX_LEN)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            return snippet[: _EXCERPT_MAX_LEN + 80]
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:_EXCERPT_MAX_LEN]


def build_position_candidates(
    chunks: Iterable[Any],
    chunk_indices: Iterable[int],
    distances: Iterable[float] | None = None,
    *,
    max_positions: int = _DEFAULT_MAX_POSITIONS,
) -> list[PositionCandidate]:
    """
    Agrège les chunks FAISS en positions SH à 4 chiffres classées par pertinence.
    """
    chunk_list = list(chunks)
    indices = [int(i) for i in chunk_indices if i is not None and int(i) >= 0]
    dist_list = list(distances) if distances is not None else []
    if not indices:
        return []

    position_scores: dict[str, float] = defaultdict(float)
    position_codes: dict[str, list[str]] = defaultdict(list)
    position_excerpt_source: dict[str, tuple[int, str]] = {}

    for rank, chunk_idx in enumerate(indices):
        if chunk_idx >= len(chunk_list):
            continue
        text = _chunk_text(chunk_list[chunk_idx])
        if not text.strip():
            continue
        dist_weight = 1.0
        if rank < len(dist_list):
            try:
                dist_weight = 1.0 / (1.0 + max(float(dist_list[rank]), 0.0))
            except (TypeError, ValueError):
                dist_weight = 1.0
        rank_weight = 1.0 / (rank + 1)
        weight = rank_weight * dist_weight

        codes = extract_tariff_codes_from_text(text)
        if not codes:
            continue

        seen_positions: set[str] = set()
        for code in codes:
            position = position_code_from_hs(code)
            if not position or len(re.sub(r"\D", "", position)) < 4:
                continue
            position_scores[position] += weight
            if code not in position_codes[position]:
                position_codes[position].append(code)
            if position not in seen_positions:
                seen_positions.add(position)
                previous = position_excerpt_source.get(position)
                if not previous or weight > position_scores[position]:
                    position_excerpt_source[position] = (chunk_idx, text)

    ranked = sorted(position_scores.items(), key=lambda item: item[1], reverse=True)
    candidates: list[PositionCandidate] = []
    for position, score in ranked[: max(1, int(max_positions))]:
        matched = position_codes.get(position, [])
        _, source_text = position_excerpt_source.get(position, (-1, ""))
        chapter = re.sub(r"\D", "", position)[:2]
        candidates.append(
            PositionCandidate(
                position_code=position,
                label=_position_label(position, matched),
                score=score,
                chapter=chapter,
                excerpt=_build_excerpt(source_text, matched),
                matched_codes=matched,
            )
        )
    return candidates


def format_candidate_set_prompt(
    candidates: list[PositionCandidate],
    *,
    rejected_note: str = "",
) -> str:
    """Bloc prompt imposant le choix parmi les positions candidates."""
    if not candidates:
        return (
            "Aucune position TEC candidate trouvee dans l'index local pour cette requete. "
            "Tu DOIS quand meme retourner une classification avec le chapitre le plus probable "
            "base sur ta connaissance du produit et l'identification produit ci-dessus. "
            "Utilise un code a 4 chiffres (XX.XX), confidence <= 40, classification_status = provisoire. "
            "Ne retourne JAMAIS classifications = [].\n"
        )

    lines = [
        "POSITIONS TEC CANDIDATES (VERROUILLAGE OBLIGATOIRE) :",
        "Tu dois choisir UNIQUEMENT l'une des positions ci-dessous pour hs_code "
        "(format XX.XX ou sous-code appartenant a cette position).",
        "Justifie par elimination des autres candidates.",
        "",
    ]
    for index, candidate in enumerate(candidates, start=1):
        lines.append(f"{index}. Position {candidate.position_code} — {candidate.label}")
        if candidate.matched_codes:
            lines.append(f"   Codes TEC voisins : {', '.join(candidate.matched_codes[:4])}")
        if candidate.excerpt:
            lines.append(f"   Extrait TEC : {candidate.excerpt}")
        lines.append("")

    if rejected_note.strip():
        lines.append(rejected_note.strip())
        lines.append("")

    others = len(candidates)
    lines.append(
        f"INTERDIT : hs_code en dehors de ces {others} position(s). "
        "Si aucune ne convient parfaitement, retiens la moins inadequate, "
        "confidence <= 55, classification_status = provisoire, "
        "et explique les positions ecartees dans la justification."
    )
    return "\n".join(lines)


def format_merged_candidates_prompt(candidate_dicts: list[dict[str, Any]]) -> str:
    """Reconstruit le bloc prompt à partir de dicts candidats fusionnés."""
    if not candidate_dicts:
        return (
            "Aucune position TEC candidate trouvee dans l'index local pour cette requete. "
            "Tu DOIS quand meme retourner une classification avec le chapitre le plus probable "
            "base sur ta connaissance du produit et l'identification produit ci-dessus. "
            "Utilise un code a 4 chiffres (XX.XX), confidence <= 40, classification_status = provisoire. "
            "Ne retourne JAMAIS classifications = [].\n"
        )
    lines = [
        "POSITIONS TEC CANDIDATES (VERROUILLAGE OBLIGATOIRE) :",
        "Tu dois choisir UNIQUEMENT l'une des positions ci-dessous pour hs_code "
        "(format XX.XX ou sous-code appartenant a cette position).",
        "Justifie par elimination des autres candidates.",
        "",
    ]
    for idx, cd in enumerate(candidate_dicts, start=1):
        pos = cd.get("position_code", "?")
        label = cd.get("label", "")
        lines.append(f"{idx}. Position {pos} — {label}")
        excerpt = cd.get("excerpt", "")
        if excerpt:
            lines.append(f"   Extrait TEC : {excerpt[:320]}")
        lines.append("")
    lines.append(
        f"INTERDIT : hs_code en dehors de ces {len(candidate_dicts)} position(s). "
        "Si aucune ne convient parfaitement, retiens la moins inadequate, "
        "confidence <= 55, classification_status = provisoire, "
        "et explique les positions ecartees dans la justification."
    )
    return "\n".join(lines)


def retrieve_locked_tec_context(
    query: str,
    chunks: Iterable[Any],
    index: Any,
    *,
    search_fn: Any,
    k: int = 8,
    max_positions: int = _DEFAULT_MAX_POSITIONS,
) -> tuple[str, list[dict[str, Any]]]:
    """Recherche FAISS + construction du bloc positions candidates (sans dump brut de chunks)."""
    indices, distances = search_fn(query, index, k=k)
    if indices is None:
        return format_candidate_set_prompt([]), []
    if hasattr(indices, "size") and indices.size == 0:
        return format_candidate_set_prompt([]), []
    if not hasattr(indices, "size") and len(indices) == 0:
        return format_candidate_set_prompt([]), []

    row_indices = indices[0]
    row_distances = distances[0] if distances is not None and (
        (hasattr(distances, "size") and distances.size > 0) or
        (not hasattr(distances, "size") and len(distances) > 0)
    ) else []
    candidates = build_position_candidates(
        chunks,
        row_indices,
        row_distances,
        max_positions=max_positions,
    )
    return format_candidate_set_prompt(candidates), [item.to_dict() for item in candidates]


def _hs_matches_candidate(hs_code: str, candidate: dict[str, Any]) -> bool:
    position = str(candidate.get("position_code") or "").strip()
    if not position:
        return False
    if position_code_from_hs(hs_code) == position:
        return True
    hs_digits = re.sub(r"\D", "", hs_code or "")
    pos_digits = re.sub(r"\D", "", position)
    if hs_digits.startswith(pos_digits):
        return True
    for code in candidate.get("matched_codes") or []:
        code_digits = re.sub(r"\D", "", str(code))
        if hs_digits and code_digits and hs_digits.startswith(code_digits[: min(len(code_digits), len(hs_digits))]):
            return True
        if position_code_from_hs(str(code)) == position and hs_digits.startswith(pos_digits):
            return True
    return False


def enforce_candidate_set_on_item(
    item: dict[str, Any],
    candidates: list[dict[str, Any]] | None,
) -> bool:
    """
    Ramène hs_code dans l'ensemble des positions candidates si le LLM a divergé.
    Retourne True si une correction a été appliquée.
    """
    if not isinstance(item, dict) or not candidates:
        return False

    hs = str(item.get("hs_code") or "").strip()
    if not hs or not re.sub(r"\D", "", hs):
        return False

    for candidate in candidates:
        if _hs_matches_candidate(hs, candidate):
            item["tec_position_candidates"] = candidates
            item["tec_candidate_locked"] = True
            return False

    top = candidates[0]
    target = str(top.get("position_code") or "").strip()
    if not target:
        return False

    item.setdefault("hs_code_suggested", hs)
    item["hs_code"] = target
    item["classification_status"] = "provisoire"
    try:
        current = int(round(float(item.get("confidence") or 90)))
    except (TypeError, ValueError):
        current = 90
    item["confidence"] = min(current, 55)

    allowed = ", ".join(str(c.get("position_code") or "") for c in candidates[:3])
    correction = (
        f"Hypothese LLM {hs} hors positions TEC candidates ({allowed}); "
        f"ramenee a {target}."
    )
    item["tec_candidate_correction"] = correction
    item["tec_position_candidates"] = candidates
    item["tec_candidate_locked"] = True

    justification = str(item.get("justification") or "").strip()
    if correction not in justification:
        item["justification"] = f"{correction} {justification}".strip()

    label = str(top.get("label") or "").strip()
    if label:
        item["position_label"] = label
    return True


def attach_candidates_to_classifications(
    classifications: list[Any],
    product_identifications: list[dict[str, Any]] | None,
) -> None:
    """Copie les candidates FAISS sur chaque ligne de classification."""
    if not product_identifications:
        return
    for index, item in enumerate(classifications):
        if not isinstance(item, dict) or index >= len(product_identifications):
            continue
        entry = product_identifications[index]
        if not isinstance(entry, dict):
            continue
        candidates = entry.get("tec_position_candidates")
        if isinstance(candidates, list) and candidates:
            item["tec_position_candidates"] = candidates
            enforce_candidate_set_on_item(item, candidates)
