"""Verrouillage des positions TEC candidates (TOP N) avant/après le LLM."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

import unicodedata

from .tariff_labels import lookup_position_label, list_subpositions_for_position
from .tariff_metadata import get_position_heading
from .tariff_position_rules import position_code_from_hs

try:
    from .config.settings import Config
except ImportError:  # pragma: no cover
    class Config:  # type: ignore[no-redef]
        MOSAM_FAISS_TOP_K = 20
        MOSAM_MAX_CANDIDATE_POSITIONS = 15

_TARIFF_CODE_RE = re.compile(r"\b(\d{4}\.\d{2}(?:\.\d{2}(?:\.\d{2})?)?)\b")
_DEFAULT_MAX_POSITIONS = max(1, int(getattr(Config, "MOSAM_MAX_CANDIDATE_POSITIONS", 15)))
_DEFAULT_FAISS_K = max(1, int(getattr(Config, "MOSAM_FAISS_TOP_K", 20)))
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


def _format_subpositions_block(position_code: str, max_items: int = 15) -> str:
    """Build a compact list of sub-positions for a given 4-digit position.

    Groups by 6-digit heading (XXXX.XX) to avoid showing every 8/10-digit
    sub-position individually.  This gives the LLM a clear view of all the
    "drawers" within a position without excessive detail.
    """
    subpos = list_subpositions_for_position(position_code)
    if not subpos:
        return ""

    headings_seen: dict[str, str] = {}
    for code, label in subpos:
        digits = re.sub(r"\D", "", code)
        if len(digits) >= 6:
            heading_key = f"{digits[:4]}.{digits[4:6]}"
        else:
            heading_key = code
        if heading_key not in headings_seen:
            headings_seen[heading_key] = label

    lines = []
    items = list(headings_seen.items())
    for code, label in items[:max_items]:
        lines.append(f"      - {code} : {label[:90]}")
    if len(items) > max_items:
        lines.append(f"      ... et {len(items) - max_items} autres sous-positions")
    return "\n".join(lines)


def _elimination_methodology_lines(candidate_count: int) -> list[str]:
    """Instructions d'analyse par elimination (compatible / incompatible / pourquoi)."""
    return [
        "METHODE D'ANALYSE PAR ELIMINATION (OBLIGATOIRE) :",
        "Tu es meilleur pour ELIMINER que pour deviner. Ne choisis pas immediatement « le meilleur code ».",
        f"1. Pour CHACUNE des {candidate_count} position(s) ci-dessous, evalue :",
        "   - compatible : le libelle et les sous-positions TEC decrivent la nature technique du produit ;",
        "   - incompatible : motif precis (fonction differente, type d'appareil, matiere, chapitre ecarte) ;",
        "   - incertain : information manquante pour trancher.",
        "2. Dans la justification, liste chaque position avec son verdict (compatible / incompatible / incertain) "
        "et le motif en une phrase.",
        "3. Choisis hs_code UNIQUEMENT parmi les positions compatibles.",
        "4. S'il reste plusieurs compatibles, prefere la plus specifique (RGI 3 a).",
        "5. Si aucune n'est clairement compatible, retiens la moins inadequate, "
        "confidence <= 55, classification_status = provisoire.",
        "",
    ]


def limit_position_candidates(
    candidate_dicts: list[dict[str, Any]],
    *,
    max_positions: int | None = None,
) -> list[dict[str, Any]]:
    """Limite le nombre de positions envoyees au LLM apres fusion multi-sources."""
    cap = max(1, int(max_positions or _DEFAULT_MAX_POSITIONS))
    if len(candidate_dicts) <= cap:
        return candidate_dicts
    ranked = sorted(
        candidate_dicts,
        key=lambda item: float(item.get("score") or 0),
        reverse=True,
    )
    return ranked[:cap]


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
        "Le contexte TEC local contient les positions suivantes a analyser.",
        *_elimination_methodology_lines(len(candidates)),
    ]
    for index, candidate in enumerate(candidates, start=1):
        lines.append(f"{index}. Position {candidate.position_code} — {candidate.label}")
        subpos_block = _format_subpositions_block(candidate.position_code)
        if subpos_block:
            lines.append(f"   Sous-positions TEC :")
            lines.append(subpos_block)
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
        "Format hs_code : XX.XX ou sous-code appartenant a l'une des positions compatibles. "
        "La justification DOIT contenir l'analyse compatible/incompatible de chaque position."
    )
    return "\n".join(lines)


def _normalize_for_match(text: str) -> str:
    """Normalize for matching: lowercase, strip accents and punctuation."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _compute_subposition_affinity(
    position_code: str,
    product_type: str,
    function_usage: str,
    family: str = "",
) -> tuple[float, str]:
    """Score how well a position's sub-positions match the product identification.

    Returns (score, best_matching_sub_position_label).
    """
    subpos = list_subpositions_for_position(position_code)
    if not subpos:
        return 0.0, ""

    heading = lookup_position_label(position_code) or ""

    search_parts = []
    for text in [product_type, function_usage, family]:
        text = (text or "").strip()
        if text:
            search_parts.extend(_normalize_for_match(text).split())

    search_terms = {t for t in search_parts if len(t) >= 4}
    if not search_terms:
        return 0.0, ""

    best_score = 0.0
    best_label = ""

    for _code, label in subpos:
        norm_label = _normalize_for_match(label)
        label_words = set(norm_label.split())
        matches = 0
        for term in search_terms:
            if term in label_words:
                matches += 1
            elif any(term in w or w in term for w in label_words if len(w) >= 4):
                matches += 0.5
        score = matches / len(search_terms) if search_terms else 0
        if score > best_score:
            best_score = score
            best_label = label

    # Also check position heading
    norm_heading = _normalize_for_match(heading)
    heading_words = set(norm_heading.split())
    h_matches = 0
    for term in search_terms:
        if term in heading_words:
            h_matches += 1
        elif any(term in w or w in term for w in heading_words if len(w) >= 4):
            h_matches += 0.5
    h_score = h_matches / len(search_terms) if search_terms else 0
    if h_score > best_score:
        best_score = h_score
        best_label = heading

    return best_score, best_label


def rerank_candidates_by_affinity(
    candidate_dicts: list[dict[str, Any]],
    product_type: str = "",
    function_usage: str = "",
    family: str = "",
) -> list[dict[str, Any]]:
    """Add affinity notes to candidates and promote strong matches.

    Only reorders when a non-first candidate has significantly higher
    affinity than the current first candidate.  Otherwise just adds
    notes without changing order.
    """
    if not candidate_dicts:
        return candidate_dicts

    scored: list[tuple[dict[str, Any], float, str]] = []
    for cd in candidate_dicts:
        pos = cd.get("position_code", "")
        aff_score, aff_label = _compute_subposition_affinity(
            pos, product_type, function_usage, family,
        )
        cd_copy = dict(cd)
        if aff_score > 0.15 and aff_label:
            cd_copy["affinity_note"] = (
                f"Correspondance avec le produit : '{aff_label}'"
            )
        scored.append((cd_copy, aff_score, aff_label))

    if len(scored) < 2:
        return [s[0] for s in scored]

    first_score = scored[0][1]
    best_idx = 0
    best_score = first_score
    for idx, (_, score, _) in enumerate(scored[1:], 1):
        if score > best_score:
            best_score = score
            best_idx = idx

    # Only promote if the best match is significantly better than the first
    if best_idx > 0 and best_score >= 0.3 and best_score > first_score + 0.15:
        promoted = scored.pop(best_idx)
        scored.insert(0, promoted)

    return [s[0] for s in scored]


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
        "Le contexte TEC local contient les positions suivantes a analyser.",
        *_elimination_methodology_lines(len(candidate_dicts)),
    ]
    for idx, cd in enumerate(candidate_dicts, start=1):
        pos = cd.get("position_code", "?")
        label = cd.get("label", "")
        affinity = cd.get("affinity_note", "")
        marker = " *** MEILLEURE CORRESPONDANCE ***" if idx == 1 and affinity else ""
        lines.append(f"{idx}. Position {pos} — {label}{marker}")
        if affinity:
            lines.append(f"   >> {affinity}")
        subpos_block = _format_subpositions_block(pos)
        if subpos_block:
            lines.append(f"   Sous-positions TEC :")
            lines.append(subpos_block)
        excerpt = cd.get("excerpt", "")
        if excerpt:
            lines.append(f"   Extrait TEC : {excerpt[:320]}")
        lines.append("")
    lines.append(
        f"INTERDIT : hs_code en dehors de ces {len(candidate_dicts)} position(s). "
        "Format hs_code : XX.XX ou sous-code appartenant a l'une des positions compatibles. "
        "La justification DOIT contenir l'analyse compatible/incompatible de chaque position."
    )
    if candidate_dicts and candidate_dicts[0].get("affinity_note"):
        lines.append(
            "NOTE : La position marquee '*** MEILLEURE CORRESPONDANCE ***' a ete identifiee "
            "par analyse textuelle comme la plus proche du type de produit. "
            "Justifie si tu choisis une autre position."
        )
    return "\n".join(lines)


def retrieve_locked_tec_context(
    query: str,
    chunks: Iterable[Any],
    index: Any,
    *,
    search_fn: Any,
    k: int | None = None,
    max_positions: int | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Recherche FAISS + construction du bloc positions candidates (sans dump brut de chunks)."""
    faiss_k = max(1, int(k if k is not None else _DEFAULT_FAISS_K))
    position_cap = max(1, int(max_positions if max_positions is not None else _DEFAULT_MAX_POSITIONS))
    indices, distances = search_fn(query, index, k=faiss_k)
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
        max_positions=position_cap,
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
