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
from .telemetry import increment_telemetry

try:
    from .config.settings import Config
except ImportError:  # pragma: no cover
    class Config:  # type: ignore[no-redef]
        MOSAM_FAISS_TOP_K = 16
        MOSAM_MAX_CANDIDATE_POSITIONS = 8
        MOSAM_TEC_EXCERPT_MAX_CHARS = 180
        MOSAM_TEC_SUBPOSITIONS_MAX_ITEMS = 8
        MOSAM_TEC_CONTEXT_COMPACT = True

_TARIFF_CODE_RE = re.compile(r"\b(\d{4}\.\d{2}(?:\.\d{2}(?:\.\d{2})?)?)\b")
_DEFAULT_MAX_POSITIONS = max(1, int(getattr(Config, "MOSAM_MAX_CANDIDATE_POSITIONS", 8)))
_DEFAULT_FAISS_K = max(1, int(getattr(Config, "MOSAM_FAISS_TOP_K", 16)))
_EXCERPT_MAX_LEN = max(0, int(getattr(Config, "MOSAM_TEC_EXCERPT_MAX_CHARS", 180)))
_SUBPOSITIONS_MAX_ITEMS = max(0, int(getattr(Config, "MOSAM_TEC_SUBPOSITIONS_MAX_ITEMS", 8)))
_COMPACT_CONTEXT = bool(getattr(Config, "MOSAM_TEC_CONTEXT_COMPACT", True))

_PHONE_FAMILY_TERMS = {"telephone", "telephones", "smartphone", "smartphones", "cellulaire"}
_TABLET_FAMILY_TERMS = {
    "tablette", "tablettes", "tablet", "tablets", "ordinateur", "ordinateurs",
    "traitement", "information", "portatives", "portable",
}
_NETWORK_FAMILY_TERMS = {
    "transmission", "reception", "regeneration", "commutation", "telecommunication",
    "reseau", "reseaux", "donnees", "ethernet",
}
_CAMERA_FAMILY_TERMS = {
    "camera", "cameras", "television", "video", "numeriques", "numerique",
    "imagerie", "thermique", "optique", "surveillance",
}
_CINEMA_FAMILY_TERMS = {"cinematographiques", "cinematographique", "film", "pellicule"}
_STORAGE_SYSTEM_TERMS = {
    "traitement", "information", "stockage", "donnees", "unites", "unite",
    "memoire", "serveurs", "serveur", "systeme", "systemes",
}
_STORAGE_MEDIA_TERMS = {
    "supports", "support", "disques", "disque", "bandes", "bande", "cartes",
    "carte", "enregistrement", "recording", "media",
}
_SERVER_SYSTEM_TERMS = {
    "serveurs", "serveur", "unites", "unite", "traitement", "information",
    "donnees", "machines", "automatiques", "systeme", "systemes",
}
_ACCELERATOR_CARD_TERMS = {
    "parties", "accessoires", "machines", "traitement", "information",
    "cartes", "carte", "modules", "module",
}
_PLC_FAMILY_TERMS = {
    "commande", "controle", "panneaux", "panneau", "tableaux", "tableau",
    "consoles", "console", "armoires", "armoire",
}
_GENERIC_ADP_TERMS = {
    "machines", "automatiques", "traitement", "information", "portatives",
}
_VFD_FAMILY_TERMS = {
    "convertisseurs", "convertisseur", "statiques", "statique", "variateurs",
    "variateur", "redresseurs", "redresseur", "moteurs", "moteur", "electrique",
}
_HOUSEHOLD_APPLIANCE_TERMS = {
    "aspirateurs", "aspirateur", "reservoir", "reservoirs", "balais", "domestiques",
    "menagers", "menageres", "poussiere",
}
_ROBOT_FAMILY_TERMS = {"robots", "robot", "industriels", "industriel"}
_BICYCLE_PARTS_TERMS = {
    "cycles", "bicyclettes", "motocycles", "motocyclettes", "accessoires",
}
_MEDICAL_DEVICE_TERMS = {
    "seringue", "seringues", "aiguille", "aiguilles", "medical", "medicale",
    "medicaux", "medicales", "sterile", "steriles", "injection", "injecter",
    "perfusion", "chirurgical", "veterinaire",
}
_RADIOLOGY_TERMS = {
    "rayons", "radiations", "radiographie", "radiotherapie", "tomographie",
    "radiophotographie", "ionisantes", "x",
}
_DISPLAY_HEADSET_TERMS = {
    "moniteurs", "moniteur", "projecteurs", "projecteur", "affichage",
    "casques", "casque", "video", "ecran", "ecrans", "optique",
}
_TELEPHONE_TERMS = {
    "telephone", "telephones", "smartphone", "smartphones", "cellulaire",
    "cellulaires",
}


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
    if _EXCERPT_MAX_LEN <= 0:
        return ""
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


def _format_subpositions_block(position_code: str, max_items: int | None = None) -> str:
    """Build a compact list of sub-positions for a given 4-digit position.

    Groups by 6-digit heading (XXXX.XX) to avoid showing every 8/10-digit
    sub-position individually.  This gives the LLM a clear view of all the
    "drawers" within a position without excessive detail.
    """
    subpos = list_subpositions_for_position(position_code)
    if not subpos:
        return ""
    if max_items is None:
        max_items = _SUBPOSITIONS_MAX_ITEMS
    if max_items <= 0:
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
    if _COMPACT_CONTEXT:
        return [
            "METHODE D'ELIMINATION : evalue chaque position candidate "
            "(compatible / incompatible / incertain), "
            "choisis une position compatible; si aucune ne convient, propose une hypothese hors liste "
            "avec confidence <= 55.",
            "",
        ]
    return [
        "METHODE D'ANALYSE PAR ELIMINATION (OBLIGATOIRE) :",
        "Tu es meilleur pour ELIMINER que pour deviner. Ne choisis pas immediatement « le meilleur code ».",
        f"1. Pour CHACUNE des {candidate_count} position(s) ci-dessous, evalue :",
        "   - compatible : le libelle et les sous-positions TEC decrivent la nature technique du produit ;",
        "   - incompatible : motif precis (fonction differente, type d'appareil, matiere, chapitre ecarte) ;",
        "   - incertain : information manquante pour trancher.",
        "2. Dans la justification, liste chaque position avec son verdict (compatible / incompatible / incertain) "
        "et le motif en une phrase.",
        "3. Choisis hs_code parmi les positions compatibles lorsqu'il en existe une.",
        "4. S'il reste plusieurs compatibles, prefere la plus specifique (RGI 3 a).",
        "5. Si aucune n'est clairement compatible, propose le code TEC le plus plausible hors liste, "
        "confidence <= 55, classification_status = provisoire, avec justification explicite.",
        "",
    ]


def limit_position_candidates(
    candidate_dicts: list[dict[str, Any]],
    *,
    max_positions: int | None = None,
) -> list[dict[str, Any]]:
    """Keep the strongest candidates while preserving credible chapter diversity."""
    cap = max(1, int(max_positions or _DEFAULT_MAX_POSITIONS))
    deduplicated: list[dict[str, Any]] = []
    by_position: dict[str, dict[str, Any]] = {}
    for raw in candidate_dicts:
        if not isinstance(raw, dict):
            continue
        candidate = dict(raw)
        position = str(candidate.get("position_code") or "").strip()
        if not position:
            continue
        candidate.setdefault("chapter", re.sub(r"\D", "", position)[:2])
        sources = candidate.get("candidate_sources")
        if not isinstance(sources, list):
            candidate["candidate_sources"] = ["unknown"]
        existing = by_position.get(position)
        if existing is None:
            by_position[position] = candidate
            deduplicated.append(candidate)
            continue
        existing["score"] = max(
            float(existing.get("score") or 0),
            float(candidate.get("score") or 0),
        )
        existing["affinity_score"] = max(
            float(existing.get("affinity_score") or 0),
            float(candidate.get("affinity_score") or 0),
        )
        existing["candidate_sources"] = list(dict.fromkeys(
            [str(source) for source in existing.get("candidate_sources") or []]
            + [str(source) for source in candidate.get("candidate_sources") or []]
        ))
        existing["matched_codes"] = list(dict.fromkeys(
            [str(code) for code in existing.get("matched_codes") or []]
            + [str(code) for code in candidate.get("matched_codes") or []]
        ))[:8]
        for field in ("label", "excerpt", "affinity_note"):
            if not existing.get(field) and candidate.get(field):
                existing[field] = candidate[field]

    def rank_score(candidate: dict[str, Any]) -> float:
        score = float(candidate.get("score") or 0)
        affinity = float(candidate.get("affinity_score") or 0)
        compatibility = float(candidate.get("compatibility_score") or 0)
        combined = score + (4.0 * affinity) + (5.0 * compatibility)
        candidate["candidate_rank_score"] = round(combined, 4)
        return combined

    ranked = sorted(
        deduplicated,
        key=rank_score,
        reverse=True,
    )
    if len(ranked) <= cap:
        return ranked

    selected: list[dict[str, Any]] = [ranked[0]]
    selected_positions = {str(ranked[0].get("position_code") or "")}
    selected_chapters = {str(ranked[0].get("chapter") or "")}
    best_rank = max(float(ranked[0].get("candidate_rank_score") or 0), 0.001)
    diversity_target = min(3, cap)

    for candidate in ranked[1:]:
        chapter = str(candidate.get("chapter") or "")
        candidate_rank = float(candidate.get("candidate_rank_score") or 0)
        affinity = float(candidate.get("affinity_score") or 0)
        credible = candidate_rank >= best_rank * 0.15 or affinity >= 0.15
        if chapter and chapter not in selected_chapters and credible:
            selected.append(candidate)
            selected_positions.add(str(candidate.get("position_code") or ""))
            selected_chapters.add(chapter)
            if len(selected_chapters) >= diversity_target or len(selected) >= cap:
                break

    for candidate in ranked:
        position = str(candidate.get("position_code") or "")
        if position in selected_positions:
            continue
        selected.append(candidate)
        selected_positions.add(position)
        if len(selected) >= cap:
            break
    return selected[:cap]


def summarize_candidate_evidence(candidate_dicts: list[dict[str, Any]]) -> dict[str, Any]:
    """Return tariff-neutral diagnostics for candidate-recall monitoring."""
    positions = [
        str(candidate.get("position_code") or "").strip()
        for candidate in candidate_dicts
        if isinstance(candidate, dict) and str(candidate.get("position_code") or "").strip()
    ]
    chapters = sorted({re.sub(r"\D", "", position)[:2] for position in positions})
    affinities = [
        float(candidate.get("affinity_score") or 0)
        for candidate in candidate_dicts
        if isinstance(candidate, dict)
    ]
    sources = sorted({
        str(source)
        for candidate in candidate_dicts
        if isinstance(candidate, dict)
        for source in (candidate.get("candidate_sources") or [])
    })
    chapter_scores: dict[str, float] = defaultdict(float)
    chapter_positions: dict[str, list[str]] = defaultdict(list)
    for candidate in candidate_dicts:
        if not isinstance(candidate, dict):
            continue
        position = str(candidate.get("position_code") or "").strip()
        chapter = re.sub(r"\D", "", position)[:2]
        if not chapter:
            continue
        rank_score = float(candidate.get("candidate_rank_score") or 0)
        if rank_score <= 0:
            rank_score = float(candidate.get("score") or 0) + 4.0 * float(
                candidate.get("affinity_score") or 0
            )
        chapter_scores[chapter] += max(rank_score, 0.0)
        if position and position not in chapter_positions[chapter]:
            chapter_positions[chapter].append(position)
    chapter_ranking = [
        {
            "chapter": chapter,
            "score": round(score, 4),
            "positions": chapter_positions[chapter],
        }
        for chapter, score in sorted(
            chapter_scores.items(), key=lambda entry: (-entry[1], entry[0])
        )
    ]
    return {
        "candidate_count": len(positions),
        "positions": positions,
        "chapters": chapters,
        "chapter_count": len(chapters),
        "max_affinity": round(max(affinities, default=0.0), 3),
        "sources": sources,
        "chapter_ranking": chapter_ranking,
    }


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
        "Prioriser ces positions candidates lorsqu'elles sont compatibles avec le produit.",
        "Si aucune position n'est compatible, proposer le code TEC le plus plausible hors liste, "
        "avec classification_status = provisoire et confidence <= 55.",
        *_elimination_methodology_lines(len(candidates)),
    ]
    for index, candidate in enumerate(candidates, start=1):
        lines.append(f"{index}. Position {candidate.position_code} — {candidate.label}")
        subpos_block = _format_subpositions_block(candidate.position_code)
        if subpos_block:
            lines.append("   Sous-positions TEC :")
            lines.append(subpos_block)
        if candidate.matched_codes:
            lines.append(f"   Codes voisins : {', '.join(candidate.matched_codes[:3])}")
        if candidate.excerpt and not _COMPACT_CONTEXT:
            lines.append(f"   Extrait TEC : {candidate.excerpt}")
        lines.append("")

    if rejected_note.strip():
        lines.append(rejected_note.strip())
        lines.append("")

    others = len(candidates)
    lines.append(
        f"GARDE-FOU : evaluer d'abord ces {others} position(s). "
        "Format hs_code : XX.XX ou sous-code TEC. "
        "Tout choix hors liste doit rester provisoire et expliquer pourquoi chaque candidat est incompatible."
    )
    return "\n".join(lines)


def _normalize_for_match(text: str) -> str:
    """Normalize for matching: lowercase, strip accents and punctuation."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _matching_terms(label_terms: set[str], expected_terms: set[str]) -> int:
    score = 0
    for term in expected_terms:
        if term in label_terms:
            score += 1
    return score


def _compatibility_from_product_family(
    label: str,
    product_type: str,
    function_usage: str,
    family: str = "",
) -> tuple[float, str]:
    """Estimate whether a TEC heading family matches the product's technical nature."""
    combined = _normalize_for_match(" ".join([product_type, function_usage, family]))
    label_norm = _normalize_for_match(label)
    if not combined or not label_norm:
        return 0.0, ""

    descriptor_terms = set(combined.split())
    label_terms = set(label_norm.split())
    notes: list[str] = []
    score = 0.0

    is_tablet = bool(descriptor_terms & {"tablette", "tablet"})
    is_network = bool(descriptor_terms & {"switching", "switch", "commutation", "routeur", "router", "ethernet"})
    is_camera = bool(descriptor_terms & {"camera", "imagerie", "video", "thermique", "multisenseur", "multispectral"})
    is_storage_system = "storage" in descriptor_terms or "stockage" in descriptor_terms or "baie" in descriptor_terms
    is_storage_media = bool(
        descriptor_terms & {"ssd", "nvme", "disque", "disques", "hard", "drive", "stockage"}
    ) and not is_storage_system
    is_server_system = bool(
        descriptor_terms & {"serveur", "server", "rack", "compute"}
    )
    is_accelerator_card = bool(
        descriptor_terms & {"accelerateur", "accelerator", "gpu", "pcie", "expansion"}
    )
    is_plc = bool(descriptor_terms & {"plc", "automate", "programmable", "controleur", "controller"})
    is_vfd = bool(descriptor_terms & {"variateur", "convertisseur", "inverter", "vfd", "drive", "frequence", "moteur"})
    is_robot = bool(descriptor_terms & {"robot", "robotique", "robotise", "robotisee"})
    is_mixed_reality_display = bool(
        descriptor_terms
        & {"realite", "virtuelle", "mixte", "headset", "casque", "affichage", "immersif", "spatial"}
    )
    is_medical_device = bool(
        descriptor_terms & {"seringue", "seringues", "syringe", "medical", "medicale", "injection", "aiguille"}
    )

    if is_tablet:
        positive = _matching_terms(label_terms, _TABLET_FAMILY_TERMS)
        negative = _matching_terms(label_terms, _PHONE_FAMILY_TERMS)
        score += 0.14 * positive
        score -= 0.35 * negative
        if positive:
            notes.append("famille ordinateur/tablette")
        if negative:
            notes.append("famille telephone incompatible")

    if is_network:
        positive = _matching_terms(label_terms, _NETWORK_FAMILY_TERMS)
        negative = _matching_terms(label_terms, _PHONE_FAMILY_TERMS)
        score += 0.14 * positive
        score -= 0.35 * negative
        if positive:
            notes.append("equipement reseau compatible")
        if negative:
            notes.append("famille smartphone incompatible")

    if is_camera:
        positive = _matching_terms(label_terms, _CAMERA_FAMILY_TERMS)
        negative = _matching_terms(label_terms, _CINEMA_FAMILY_TERMS | _PHONE_FAMILY_TERMS)
        score += 0.14 * positive
        score -= 0.35 * negative
        if positive:
            notes.append("famille camera compatible")
        if negative:
            notes.append("famille cinema/telephone incompatible")

    if is_storage_system:
        positive = _matching_terms(label_terms, _STORAGE_SYSTEM_TERMS)
        negative = _matching_terms(label_terms, _STORAGE_MEDIA_TERMS)
        score += 0.12 * positive
        score -= 0.28 * negative
        if positive:
            notes.append("systeme de stockage compatible")
        if negative:
            notes.append("support media incompatible")

    if is_storage_media:
        positive = _matching_terms(label_terms, _STORAGE_SYSTEM_TERMS)
        negative = _matching_terms(label_terms, _PHONE_FAMILY_TERMS)
        score += 0.08 * positive
        score -= 0.18 * negative
        if positive:
            notes.append("support ou unite de stockage compatible")
        if negative:
            notes.append("famille telephone incompatible")

    if is_server_system:
        positive = _matching_terms(label_terms, _SERVER_SYSTEM_TERMS)
        negative = _matching_terms(label_terms, _PHONE_FAMILY_TERMS | _DISPLAY_HEADSET_TERMS)
        score += 0.14 * positive
        score -= 0.24 * negative
        if positive:
            notes.append("serveur ou unite ADP compatible")
        if negative:
            notes.append("famille telephone/affichage seule incompatible")

    if is_accelerator_card:
        positive = _matching_terms(label_terms, _ACCELERATOR_CARD_TERMS)
        negative = _matching_terms(label_terms, _PHONE_FAMILY_TERMS | _CAMERA_FAMILY_TERMS)
        score += 0.13 * positive
        score -= 0.24 * negative
        if positive:
            notes.append("carte ou accessoire ADP compatible")
        if negative:
            notes.append("famille telephone/camera incompatible")

    if is_plc:
        positive = _matching_terms(label_terms, _PLC_FAMILY_TERMS)
        negative = _matching_terms(label_terms, _GENERIC_ADP_TERMS - {"traitement", "information"})
        score += 0.14 * positive
        score -= 0.12 * negative
        if positive:
            notes.append("commande industrielle compatible")
        if negative:
            notes.append("machine ADP generique moins probable")

    if is_vfd:
        positive = _matching_terms(label_terms, _VFD_FAMILY_TERMS)
        negative = _matching_terms(label_terms, _HOUSEHOLD_APPLIANCE_TERMS)
        score += 0.15 * positive
        score -= 0.4 * negative
        if positive:
            notes.append("convertisseur/variateur compatible")
        if negative:
            notes.append("appareil menager incompatible")

    if is_robot:
        positive = _matching_terms(label_terms, _ROBOT_FAMILY_TERMS)
        negative = _matching_terms(label_terms, _BICYCLE_PARTS_TERMS)
        score += 0.16 * positive
        score -= 0.4 * negative
        if positive:
            notes.append("robot industriel compatible")
        if negative:
            notes.append("pieces de cycles incompatibles")

    if is_medical_device:
        positive = _matching_terms(label_terms, _MEDICAL_DEVICE_TERMS)
        negative = _matching_terms(label_terms, _RADIOLOGY_TERMS)
        score += 0.14 * positive
        score -= 0.45 * negative
        if positive:
            notes.append("dispositif medical compatible")
        if negative:
            notes.append("radiologie/imagerie incompatible")

    if is_mixed_reality_display:
        positive = _matching_terms(label_terms, _DISPLAY_HEADSET_TERMS)
        negative = _matching_terms(label_terms, _TELEPHONE_TERMS)
        score += 0.14 * positive
        score -= 0.22 * negative
        if positive:
            notes.append("appareil d affichage immersif compatible")
        if negative:
            notes.append("famille telephone incompatible")

    score = max(-1.0, min(1.0, score))
    return score, "; ".join(dict.fromkeys(notes))


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
        cd_copy["affinity_score"] = round(aff_score, 4)
        compatibility_score, compatibility_note = _compatibility_from_product_family(
            f"{cd.get('label', '')} {cd.get('excerpt', '')}",
            product_type,
            function_usage,
            family,
        )
        cd_copy["compatibility_score"] = round(compatibility_score, 4)
        if aff_score > 0.15 and aff_label:
            cd_copy["affinity_note"] = (
                f"Correspondance avec le produit : '{aff_label}'"
            )
        if compatibility_score >= 0.2 and compatibility_note:
            cd_copy["compatibility_note"] = compatibility_note
        elif compatibility_score <= -0.2 and compatibility_note:
            cd_copy["compatibility_warning"] = compatibility_note
        scored.append((cd_copy, aff_score, aff_label))

    if len(scored) < 2:
        return [s[0] for s in scored]

    def combined_rank(entry: tuple[dict[str, Any], float, str]) -> float:
        candidate, score, _ = entry
        compatibility = float(candidate.get("compatibility_score") or 0)
        return score + (5.0 * compatibility)

    first_rank = combined_rank(scored[0])
    best_idx = 0
    best_rank = first_rank
    for idx, entry in enumerate(scored[1:], 1):
        entry_rank = combined_rank(entry)
        if entry_rank > best_rank:
            best_rank = entry_rank
            best_idx = idx

    if best_idx > 0 and best_rank > first_rank + 0.2:
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
        "Prioriser ces positions candidates lorsqu'elles sont compatibles avec le produit.",
        "Si aucune position n'est compatible, proposer le code TEC le plus plausible hors liste, "
        "avec classification_status = provisoire et confidence <= 55.",
        *_elimination_methodology_lines(len(candidate_dicts)),
    ]
    hierarchy = summarize_candidate_evidence(candidate_dicts).get("chapter_ranking") or []
    if hierarchy:
        chapter_line = "; ".join(
            f"chapitre {entry['chapter']} -> {', '.join(entry['positions'])}"
            for entry in hierarchy[:4]
        )
        lines.extend([
            "DECISION HIERARCHIQUE : valider d'abord le chapitre par nature technique, "
            "puis comparer les positions de ce chapitre.",
            f"Chapitres et positions candidates : {chapter_line}",
            "",
        ])
    for idx, cd in enumerate(candidate_dicts, start=1):
        pos = cd.get("position_code", "?")
        label = cd.get("label", "")
        affinity = cd.get("affinity_note", "")
        compatibility = cd.get("compatibility_note", "")
        warning = cd.get("compatibility_warning", "")
        marker = " *** MEILLEURE CORRESPONDANCE ***" if idx == 1 and affinity else ""
        lines.append(f"{idx}. Position {pos} — {label}{marker}")
        if affinity:
            lines.append(f"   >> {affinity}")
        if compatibility:
            lines.append(f"   >> Compatibilite fonctionnelle : {compatibility}")
        if warning:
            lines.append(f"   >> Alerte fonctionnelle : {warning}")
        subpos_block = _format_subpositions_block(pos)
        if subpos_block:
            lines.append("   Sous-positions TEC :")
            lines.append(subpos_block)
        excerpt = cd.get("excerpt", "")
        if excerpt and not _COMPACT_CONTEXT:
            lines.append(f"   Extrait TEC : {excerpt[:_EXCERPT_MAX_LEN]}")
        lines.append("")
    lines.append(
        f"GARDE-FOU : evaluer d'abord ces {len(candidate_dicts)} position(s). "
        "Format hs_code : XX.XX ou sous-code TEC. "
        "Tout choix hors liste doit rester provisoire et expliquer pourquoi chaque candidat est incompatible."
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
    candidate_dicts = [item.to_dict() for item in candidates]
    for candidate in candidate_dicts:
        candidate["candidate_sources"] = ["faiss"]
    return format_candidate_set_prompt(candidates), candidate_dicts


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
    Conserve le code du LLM lorsqu'il sort du jeu de candidats, mais le marque
    provisoire. La recherche vectorielle peut manquer la bonne position et ne
    doit pas transformer automatiquement un produit fini en matière première.
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
            selected_affinity = float(candidate.get("affinity_score") or 0)
            strongest = max(
                candidates,
                key=lambda entry: float(entry.get("affinity_score") or 0),
            )
            strongest_affinity = float(strongest.get("affinity_score") or 0)
            strongest_position = str(strongest.get("position_code") or "")
            selected_position = str(candidate.get("position_code") or "")
            if (
                strongest_position != selected_position
                and strongest_affinity >= 0.25
                and strongest_affinity >= selected_affinity + 0.15
            ):
                item["classification_status"] = "provisoire"
                try:
                    current = int(round(float(item.get("confidence") or 90)))
                except (TypeError, ValueError):
                    current = 90
                item["confidence"] = min(current, 55)
                try:
                    classification_confidence = int(round(float(
                        item.get("classification_confidence") or current
                    )))
                except (TypeError, ValueError):
                    classification_confidence = current
                item["classification_confidence"] = min(classification_confidence, 55)
                warning = (
                    f"La position {selected_position} appartient aux candidats TEC, mais son affinite "
                    f"fonctionnelle ({selected_affinity:.2f}) est inferieure a l'alternative "
                    f"{strongest_position} ({strongest_affinity:.2f}); validation humaine requise."
                )
                item["candidate_evidence_weak"] = True
                item["candidate_evidence_warning"] = warning
                justification = str(item.get("justification") or "").strip()
                if warning not in justification:
                    item["justification"] = f"[Controle candidats] {warning} {justification}".strip()
                increment_telemetry("candidate_weak_selections")
            return False

    item["classification_status"] = "provisoire"
    try:
        current = int(round(float(item.get("confidence") or 90)))
    except (TypeError, ValueError):
        current = 90
    item["confidence"] = min(current, 55)
    try:
        classification_confidence = int(round(float(
            item.get("classification_confidence") or current
        )))
    except (TypeError, ValueError):
        classification_confidence = current
    item["classification_confidence"] = min(classification_confidence, 55)

    allowed = ", ".join(str(c.get("position_code") or "") for c in candidates[:3])
    warning = (
        f"Hypothese {hs} hors positions TEC candidates ({allowed}); "
        "code conserve provisoirement car aucun candidat ne doit etre impose sans compatibilite produit."
    )
    item["tec_candidate_warning"] = warning
    item["tec_candidate_outside_set"] = True
    item["candidate_evidence_weak"] = True
    item["candidate_evidence_warning"] = warning
    item["tec_position_candidates"] = candidates
    item["tec_candidate_locked"] = False

    justification = str(item.get("justification") or "").strip()
    if warning not in justification:
        item["justification"] = f"{warning} {justification}".strip()
    increment_telemetry("candidate_outside_set_selections")
    return False


def recover_missing_heading_from_candidates(
    item: dict[str, Any],
    candidates: list[dict[str, Any]] | None,
) -> bool:
    """Recover only a strongly matched heading when the model omitted hs_code."""
    if not isinstance(item, dict) or not candidates:
        return False
    if re.sub(r"\D", "", str(item.get("hs_code") or "")):
        return False

    direct = [
        candidate
        for candidate in candidates
        if "direct_label_keywords" in (candidate.get("candidate_sources") or [])
        and float(candidate.get("score") or 0) >= 10.0
    ]
    positions = {
        str(candidate.get("position_code") or "").strip()
        for candidate in direct
        if str(candidate.get("position_code") or "").strip()
    }
    if len(positions) != 1:
        compatibility_candidates = sorted(
            [
                candidate
                for candidate in candidates
                if str(candidate.get("position_code") or "").strip()
            ],
            key=lambda candidate: (
                float(candidate.get("compatibility_score") or 0),
                float(candidate.get("affinity_score") or 0),
                float(candidate.get("score") or 0),
            ),
            reverse=True,
        )
        if not compatibility_candidates:
            return False
        strongest = compatibility_candidates[0]
        strongest_position = str(strongest.get("position_code") or "").strip()
        strongest_compatibility = float(strongest.get("compatibility_score") or 0)
        second_compatibility = (
            float(compatibility_candidates[1].get("compatibility_score") or 0)
            if len(compatibility_candidates) > 1
            else -1.0
        )
        if (
            strongest_position
            and strongest_compatibility >= 0.25
            and strongest_compatibility >= second_compatibility + 0.15
        ):
            position = strongest_position
        else:
            return False
    else:
        position = next(iter(positions))
    item["hs_code"] = position
    item["classification_status"] = "provisoire"
    try:
        current = int(round(float(item.get("confidence") or 40)))
    except (TypeError, ValueError):
        current = 40
    item["confidence"] = min(current, 40)
    try:
        classification_confidence = int(round(float(
            item.get("classification_confidence") or current
        )))
    except (TypeError, ValueError):
        classification_confidence = current
    item["classification_confidence"] = min(classification_confidence, 40)
    warning = (
        f"Le modele n'a pas fourni de code exploitable; la position {position} est conservee "
        "provisoirement car elle est l'unique correspondance directe avec les libelles TEC."
    )
    item["missing_code_recovered"] = True
    item["missing_code_recovery_warning"] = warning
    justification = str(item.get("justification") or "").strip()
    if warning not in justification:
        item["justification"] = f"[Recuperation position] {warning} {justification}".strip()
    increment_telemetry("missing_code_heading_recovered")
    return True


def enforce_candidate_evidence_cap(item: dict[str, Any]) -> bool:
    """Preserve a weak-candidate warning after completeness normalization."""
    if not isinstance(item, dict) or not item.get("candidate_evidence_weak"):
        return False
    item["classification_status"] = "provisoire"
    for field in ("confidence", "classification_confidence"):
        try:
            current = int(round(float(item.get(field) or 90)))
        except (TypeError, ValueError):
            current = 90
        item[field] = min(current, 55)
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
