"""Resolution des sous-positions a partir du referentiel TEC (pas de regles produit en dur).

Workflow pour chaque position retenue :

    Position retenue
            |
            v
    Lire toutes les sous-positions du TEC
            |
            v
    Extraire automatiquement les criteres discriminants de chaque sous-position
            |
            v
    Comparer chaque critere avec les informations connues sur la marchandise
            |
            v
    Marquer chaque sous-position :
        confirmee | exclue | impossible a verifier
            |
            v
    Analyse finale — quatre issues possibles :
        - retain_full_code : une seule sous-position confirmee
        - retain_autres : specifiques exclues, « Autres » retenue
        - stop_insufficient_criteria : arret au dernier niveau certain + manques
        - incoherent_description : aucune sous-position compatible

A chaque niveau (pas sur toutes les feuilles a la fois) :
    lire les sous-positions immediates
    -> eliminer celles dont le libelle ne correspond pas
    -> si une seule survit, la confirmer et descendre
    -> sinon arreter ou demander les criteres manquants

Chaque classification reévalue la description courante : un critère manquant lors
d'un cas précédent ne bloque pas si l'information est désormais fournie.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from .tariff_metadata import get_position_heading
from .tariff_labels import (
    get_tariff_label_index,
    lookup_heading_narrative,
    lookup_position_label,
)
from .tariff_position_rules import position_code_from_hs

_STOPWORDS = {
    "autres",
    "autre",
    "presente",
    "presentes",
    "entiere",
    "entierement",
    "etat",
    "importe",
    "importes",
    "importees",
    "pour",
    "industrie",
    "montage",
    "avec",
    "sans",
    "sous",
    "forme",
}

_GENERIC_HEADING_TOKENS = _STOPWORDS | {
    "machines",
    "machine",
    "automatiques",
    "automatique",
    "traitement",
    "information",
    "unites",
    "unite",
    "comportant",
    "meme",
    "enveloppe",
    "centrale",
    "entree",
    "sortie",
    "combinees",
    "combinee",
    "systemes",
    "systeme",
    "pouvant",
    "types",
    "suivants",
    "memoire",
    "autres",
    "presentant",
    "seulement",
    "elles",
    "quelle",
    "quelles",
    "soient",
    "deux",
    "moins",
    "plus",
    "leurs",
    "dans",
    "entre",
}


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _hs_digits(hs_code: str | None) -> str:
    return re.sub(r"\D", "", str(hs_code or ""))


def _heading_code(hs_code: str) -> str:
    digits = _hs_digits(hs_code)
    if len(digits) < 6:
        return position_code_from_hs(hs_code)
    return f"{digits[:4]}.{digits[4:6]}"


def _label_requires_mounting_industry(label: str) -> bool:
    norm = _normalize(label)
    return "industrie du montage" in norm or (
        ("demonte" in norm or "non monte" in norm) and "import" in norm
    )


def _label_is_autres_fallback(label: str) -> bool:
    norm = _normalize(label).strip(" -")
    return norm == "autres" or norm.endswith(" autres")


def _label_surface_material(label: str) -> str | None:
    norm = _normalize(label)
    match = re.search(
        r"surface exterieure en ([a-z ]{3,40})",
        norm,
    )
    if match:
        return match.group(1).strip()
    return None


def _source_mentions_mounted(source: str) -> bool:
    norm = _normalize(source)
    return any(
        token in norm
        for token in (
            "livre monte",
            "monte et neuf",
            "monte, neuf",
            "assemble",
            "monte et",
            "pret a l'emploi",
        )
    ) or bool(re.search(r"\bmonte\b", norm) and "non monte" not in norm and "demonte" not in norm)


def _source_mentions_dismounted_for_industry(source: str) -> bool:
    norm = _normalize(source)
    return any(
        token in norm
        for token in (
            "demonte",
            "non monte",
            "ckd",
            "skd",
            "industrie du montage",
            "pour le montage",
        )
    )


def _source_matches_surface_material(source: str, material_phrase: str) -> bool:
    norm = _normalize(source)
    material = _normalize(material_phrase)
    if not material:
        return False
    if material in norm:
        return True
    if re.search(rf"100\s*%\s*(?:de\s+)?{re.escape(material.split()[0])}", norm):
        return True
    return False


def _extract_definitive_exterior_material(source: str) -> str | None:
    """Matiere de surface exterieure explicitement precisee par l'utilisateur."""
    norm = _normalize(source)
    if not norm:
        return None
    materials = (
        "cuir naturel",
        "cuir",
        "textile",
        "matieres textiles",
        "polyester",
        "nylon",
        "plastique",
        "pvc",
        "toile",
    )
    if re.search(r"surface\s+exterieure\s*:", norm):
        block = norm.split("surface exterieure:", 1)[-1].split("\n")[0][:120]
        for material in materials:
            if material in block:
                return material.split()[0]
    if re.search(
        r"\b(?:exterieur|exterieure|surface)\s*:\s*(?:100\s*%|entiere(?:ment)?\s+en)\s+"
        r"(cuir|textile|polyester|nylon|plastique|pvc|toile)\b",
        norm,
    ):
        match = re.search(
            r"\b(?:exterieur|exterieure|surface)\s*:\s*(?:100\s*%|entiere(?:ment)?\s+en)\s+"
            r"(cuir|textile|polyester|nylon|plastique|pvc|toile)\b",
            norm,
        )
        return match.group(1) if match else None
    if re.search(
        r"\b(?:100\s*%|entiere(?:ment)?)\s+(?:en\s+)?(cuir|textile|polyester|nylon|plastique|pvc|toile)\s+"
        r"(?:apparent|exterieur|exterieure)\b",
        norm,
    ):
        match = re.search(
            r"\b(?:100\s*%|entiere(?:ment)?)\s+(?:en\s+)?(cuir|textile|polyester|nylon|plastique|pvc|toile)\s+"
            r"(?:apparent|exterieur|exterieure)\b",
            norm,
        )
        if match and "mixte" not in norm:
            return match.group(1)
    if re.search(
        r"\b(?:exterieur|exterieure)\s+(?:en|100\s*%)\s+(cuir|textile|polyester|nylon|plastique|pvc|toile)\b",
        norm,
    ):
        if "mixte" in norm or re.search(r"\bet\s+(?:cuir|textile|polyester|nylon)\b", norm):
            return None
        match = re.search(
            r"\b(?:exterieur|exterieure)\s+(?:en|100\s*%)\s+(cuir|textile|polyester|nylon|plastique|pvc|toile)\b",
            norm,
        )
        return match.group(1) if match else None
    return None


def _extract_identification_surface_material(source: str) -> str | None:
    """Matiere de surface deduite d'une fiche d'identification fiable (non saisie stricte)."""
    norm = _normalize(source)
    if not norm:
        return None
    patterns = (
        r"\b(?:tige|dessus|empeigne|vamp|upper|surface|exterieur|exterieure)\s+(?:en\s+)?"
        r"(cuir|textile|polyester|nylon|plastique|pvc|toile|matieres textiles)\b",
        r"\b(?:cuir|textile|polyester|nylon|plastique|pvc|toile)\s+"
        r"(?:apparent|exterieur|exterieure|en surface)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, norm)
        if match:
            return match.group(1)
    composition = re.search(
        r"composition\s*:?(.*?)(?:\n\s*(?:usage|capacite|caracteristique|caracteristiques)\s*:|$)",
        norm,
        re.DOTALL,
    )
    if composition:
        block = composition.group(1)
        for material in ("cuir", "textile", "polyester", "nylon", "plastique", "pvc", "toile"):
            if material in block:
                return material
    return None


def _extract_resolved_exterior_material(source: str, *, trust_identification: bool = False) -> str | None:
    stated = _extract_definitive_exterior_material(source)
    if stated:
        return stated
    if trust_identification:
        return _extract_identification_surface_material(source)
    return None


def _resolved_material_supports_surface(source: str, material_phrase: str) -> bool:
    norm = _normalize(source)
    material = _normalize(material_phrase)
    if not material:
        return False
    root = material.split()[0]
    if _source_matches_surface_material(source, material_phrase):
        return True
    patterns = (
        rf"\b(?:tige|dessus|empeigne|vamp|upper|surface|exterieur|exterieure)\s+(?:en\s+)?{re.escape(root)}\b",
        rf"\b{re.escape(root)}\b.{{0,40}}\b(?:tige|dessus|surface|exterieur|exterieure)\b",
        rf"composition\s*:.*?{re.escape(root)}",
    )
    return any(re.search(pattern, norm) for pattern in patterns)


def _surface_materials_compatible(stated: str, required: str) -> bool:
    stated_norm = _normalize(stated)
    required_norm = _normalize(required)
    if stated_norm in required_norm or required_norm in stated_norm:
        return True
    stated_root = stated_norm.split()[0]
    required_root = required_norm.split()[0]
    if stated_root == required_root:
        return True
    textile_like = {"textile", "polyester", "nylon", "toile", "matieres"}
    if stated_root in textile_like and any(token in required_norm for token in textile_like):
        return True
    return False


def _source_contradicts_surface_material(
    source: str,
    material_phrase: str,
    *,
    trust_identification: bool = False,
) -> bool:
    stated = _extract_resolved_exterior_material(
        source,
        trust_identification=trust_identification,
    )
    if not stated:
        return False
    return not _surface_materials_compatible(stated, material_phrase)


def _normalized_label_signature(label: str) -> str:
    clean = re.sub(r"^-+\s*", "", (label or "")).strip()
    return _normalize(clean)


SUBPOSITION_CONFIRMED = "confirmed"
SUBPOSITION_EXCLUDED = "excluded"
SUBPOSITION_UNVERIFIABLE = "unverifiable"

FINAL_RETAIN_FULL_CODE = "retain_full_code"
FINAL_RETAIN_AUTRES = "retain_autres"
FINAL_STOP_INSUFFICIENT = "stop_insufficient_criteria"
FINAL_INCOHERENT = "incoherent_description"

FINAL_DECISION_LABELS: dict[str, str] = {
    FINAL_RETAIN_FULL_CODE: "Code complet retenu",
    FINAL_RETAIN_AUTRES: "Sous-position « Autres » retenue",
    FINAL_STOP_INSUFFICIENT: "Arret — informations discriminantes manquantes",
    FINAL_INCOHERENT: "Incoherence entre la description et le TEC",
}


@dataclass
class FinalSubpositionDecision:
    outcome: str
    matched_code: str = ""
    viable: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    missing_notes: list[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "label": FINAL_DECISION_LABELS.get(self.outcome, self.outcome),
            "matched_code": self.matched_code,
            "viable": self.viable,
            "excluded": self.excluded,
            "missing_notes": self.missing_notes,
            "explanation": self.explanation,
        }

    @property
    def subdivision_status(self) -> str:
        if self.outcome in {FINAL_RETAIN_FULL_CODE, FINAL_RETAIN_AUTRES}:
            return "confirmed"
        if self.outcome == FINAL_INCOHERENT:
            return "incoherent"
        if self.outcome == FINAL_STOP_INSUFFICIENT and len(self.viable) > 1:
            return "ambiguous"
        return "insufficient"


@dataclass
class DiscriminantCriterion:
    kind: str
    label: str
    value: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "label": self.label, "value": self.value}


@dataclass
class SubpositionEvaluation:
    code: str
    label: str
    status: str
    criteria: list[DiscriminantCriterion]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "status": self.status,
            "criteria": [criterion.to_dict() for criterion in self.criteria],
            "detail": self.detail,
        }


@dataclass
class SubpositionWorkflowResult:
    evaluations: list[SubpositionEvaluation]
    final_decision: FinalSubpositionDecision

    @property
    def viable(self) -> list[str]:
        return list(self.final_decision.viable)

    @property
    def excluded(self) -> list[str]:
        return list(self.final_decision.excluded)

    @property
    def missing_notes(self) -> list[str]:
        return list(self.final_decision.missing_notes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluations": [evaluation.to_dict() for evaluation in self.evaluations],
            "final_decision": self.final_decision.to_dict(),
        }


@dataclass
class _CandidateProfile:
    is_autres: bool
    mounting: bool
    surface: str | None
    signature: str
    tokens: frozenset[str]


def _candidate_profile(label: str) -> _CandidateProfile:
    return _CandidateProfile(
        is_autres=_label_is_autres_fallback(label),
        mounting=_label_requires_mounting_industry(label),
        surface=_label_surface_material(label),
        signature=_normalized_label_signature(label),
        tokens=frozenset(_significant_label_tokens(label)),
    )


def _extract_discriminant_criteria(label: str) -> list[DiscriminantCriterion]:
    """Lit le libelle TEC et en deduit les criteres juridiquement discriminants."""
    profile = _candidate_profile(label)
    criteria: list[DiscriminantCriterion] = []
    if profile.is_autres:
        criteria.append(
            DiscriminantCriterion(
                kind="autres",
                label="Categorie residuelle",
                value="autres",
            )
        )
    if profile.mounting:
        criteria.append(
            DiscriminantCriterion(
                kind="mounting",
                label="Etat de presentation pour l'industrie du montage",
                value="demonte ou non monte",
            )
        )
    if profile.surface:
        criteria.append(
            DiscriminantCriterion(
                kind="surface",
                label="Surface exterieure",
                value=profile.surface,
            )
        )
    for token in sorted(profile.tokens):
        criteria.append(
            DiscriminantCriterion(
                kind="token",
                label="Terme du libelle TEC",
                value=token,
            )
        )
    if not criteria and profile.signature:
        criteria.append(
            DiscriminantCriterion(
                kind="signature",
                label="Libelle TEC",
                value=profile.signature[:120],
            )
        )
    return criteria


def _detail_for_subposition_status(status: str, profile: _CandidateProfile) -> str:
    if status == SUBPOSITION_CONFIRMED:
        return (
            "Criteres discriminants confirmes par les informations connues sur la marchandise."
        )
    if status == SUBPOSITION_EXCLUDED:
        return "Criteres discriminants en contradiction avec les informations connues."
    if profile.is_autres:
        return "Sous-position residuelle : verification en attente des autres candidats."
    return "Criteres discriminants non verifiables avec les informations disponibles."


def _compare_subposition_with_merchandise(
    label: str,
    source: str,
    *,
    trust_identification: bool = False,
) -> str:
    """Compare les criteres extraits du libelle TEC aux infos connues sur la marchandise."""
    profile = _candidate_profile(label)
    if profile.is_autres:
        return SUBPOSITION_UNVERIFIABLE

    if profile.mounting:
        if _source_mentions_dismounted_for_industry(source):
            return SUBPOSITION_CONFIRMED
        if _source_mentions_mounted(source):
            return SUBPOSITION_EXCLUDED
        return SUBPOSITION_UNVERIFIABLE

    if profile.surface:
        if _source_matches_surface_material(source, profile.surface):
            return SUBPOSITION_CONFIRMED
        if trust_identification and _resolved_material_supports_surface(source, profile.surface):
            return SUBPOSITION_CONFIRMED
        if _source_contradicts_surface_material(
            source,
            profile.surface,
            trust_identification=trust_identification,
        ):
            return SUBPOSITION_EXCLUDED
        return SUBPOSITION_UNVERIFIABLE

    source_norm = _normalize(source)
    source_tokens = set(re.findall(r"[a-z]{5,}", source_norm))
    if profile.tokens and profile.tokens.issubset(source_tokens):
        return SUBPOSITION_CONFIRMED
    if profile.tokens and trust_identification:
        matched = sum(1 for token in profile.tokens if _token_matches_source(token, source_norm))
        if matched and matched >= max(1, len(profile.tokens) // 2):
            return SUBPOSITION_CONFIRMED
    return SUBPOSITION_UNVERIFIABLE


def _evaluate_single_subposition(
    code: str,
    label: str,
    source: str,
    *,
    trust_identification: bool = False,
) -> SubpositionEvaluation:
    profile = _candidate_profile(label)
    criteria = _extract_discriminant_criteria(label)
    status = _compare_subposition_with_merchandise(
        label,
        source,
        trust_identification=trust_identification,
    )
    return SubpositionEvaluation(
        code=code,
        label=label,
        status=status,
        criteria=criteria,
        detail=_detail_for_subposition_status(status, profile),
    )


def _profile_discriminant_key(profile: _CandidateProfile) -> tuple[Any, ...]:
    if profile.is_autres:
        return ("autres",)
    parts: list[Any] = []
    if profile.mounting:
        parts.append(("mounting", True))
    if profile.surface:
        parts.append(("surface", _normalize(profile.surface)))
    if profile.tokens:
        parts.append(("tokens", tuple(sorted(profile.tokens))))
    if not parts:
        parts.append(("signature", profile.signature))
    return tuple(parts)


def _build_missing_notes_for_unverifiable(
    unverifiable: list[tuple[str, str, _CandidateProfile]],
    candidates: list[tuple[str, str]],
) -> list[str]:
    """Ne signale que les criteres qui distinguent encore plusieurs candidats viables."""
    if len(unverifiable) <= 1:
        return []

    varying_surfaces: set[str] = set()
    mounting_unverifiable = False
    varying_token_sets: list[frozenset[str]] = []
    varying_signatures: set[str] = set()
    has_autres = False

    for _code, _label, profile in unverifiable:
        if profile.is_autres:
            has_autres = True
            continue
        if profile.surface:
            varying_surfaces.add(_normalize(profile.surface))
        if profile.mounting:
            mounting_unverifiable = True
        if profile.tokens:
            varying_token_sets.append(profile.tokens)
        varying_signatures.add(profile.signature)

    notes: list[str] = []

    if len(varying_surfaces) > 1 or (len(varying_surfaces) == 1 and has_autres):
        materials = ", ".join(sorted(varying_surfaces))
        surface_codes = sorted(
            code
            for code, label in candidates
            if _label_surface_material(label)
            and _normalize(_label_surface_material(label) or "") in varying_surfaces
        )
        code_hint = surface_codes[0] if surface_codes else "TEC"
        if len(varying_surfaces) == 1:
            notes.append(
                f"Surface exterieure en {materials} (critere discriminant du libelle TEC {code_hint})"
            )
        else:
            notes.append(
                f"Surface exterieure (matiere apparente) : preciser parmi {materials} "
                "(criteres discriminants TEC)"
            )

    if mounting_unverifiable and has_autres:
        notes.append(
            "Etat de presentation : monte ou demonte/non monte pour l'industrie du montage "
            "(critere discriminant TEC)"
        )
    elif mounting_unverifiable and len({p.mounting for _, _, p in unverifiable if not p.is_autres}) > 1:
        notes.append(
            "Etat de presentation : monte ou demonte/non monte pour l'industrie du montage "
            "(critere discriminant TEC)"
        )

    if not notes and len(varying_signatures) > 1:
        hints: list[str] = []
        for code, label in candidates:
            if _label_is_autres_fallback(label):
                continue
            short = re.sub(r"\s+", " ", label).strip(" :")[:90]
            hints.append(f"{code} ({short})")
            if len(hints) >= 3:
                break
        if hints:
            notes.append(
                "Impossible de departager les sous-positions : preciser selon les libelles TEC "
                f"({'; '.join(hints[:3])})"
            )

    if not notes and len({_profile_discriminant_key(p) for _, _, p in unverifiable}) > 1:
        token_union: set[str] = set()
        for _code, _label, profile in unverifiable:
            if profile.tokens:
                token_union |= set(profile.tokens)
        if token_union:
            notes.append(
                "Criteres du libelle TEC non confirmes : "
                + ", ".join(sorted(token_union)[:4])
            )

    return notes[:6]


def _significant_label_tokens(label: str) -> set[str]:
    norm = _normalize(label)
    tokens = set(re.findall(r"[a-z]{5,}", norm))
    return {token for token in tokens if token not in _STOPWORDS}


def _list_distinct_headings(position_code: str) -> list[str]:
    """Sous-positions a 6 chiffres distinctes sous une position (4 chiffres)."""
    position_digits = re.sub(r"\D", "", position_code or "")
    if len(position_digits) < 4:
        return []
    index = get_tariff_label_index()
    headings: set[str] = set()
    for code in index:
        digits = _hs_digits(code)
        if digits.startswith(position_digits) and len(digits) >= 6:
            headings.add(f"{digits[:4]}.{digits[4:6]}")
    return sorted(headings)


def _token_matches_source(token: str, source_norm: str) -> bool:
    if not token or not source_norm:
        return False
    if token in source_norm:
        return True
    if len(token) >= 5 and token[:5] in source_norm:
        return True
    return False


def _heading_discriminant_tokens(heading: str, position_code: str) -> set[str]:
    narrative = lookup_heading_narrative(heading) or ""
    heading_tokens = _significant_label_tokens(narrative)
    position_tokens = _significant_label_tokens(get_position_heading(position_code) or "")
    return {token for token in heading_tokens - position_tokens - _GENERIC_HEADING_TOKENS if len(token) >= 5}


def _heading_unique_discriminants(heading: str, position_code: str, all_headings: list[str]) -> set[str]:
    mine = _heading_discriminant_tokens(heading, position_code)
    others: set[str] = set()
    for other in all_headings:
        if other != heading:
            others |= _heading_discriminant_tokens(other, position_code)
    return {token for token in mine - others if len(token) >= 5}


def _heading_confirmed_by_source(
    heading: str,
    position_code: str,
    source: str,
    all_headings: list[str],
) -> bool:
    """True si la description confirme le libelle narratif TEC de la sous-position a 6 chiffres."""
    unique = _heading_unique_discriminants(heading, position_code, all_headings)
    source_norm = _normalize(source)
    if unique and any(_token_matches_source(token, source_norm) for token in unique):
        return True

    discriminants = _heading_discriminant_tokens(heading, position_code)
    if not discriminants:
        return False
    matched = [token for token in discriminants if _token_matches_source(token, source_norm)]
    return len(matched) == len(discriminants)


def _build_heading_missing_criteria(position_code: str, headings: list[str]) -> list[str]:
    hints: list[str] = []
    for heading in headings:
        narrative = lookup_heading_narrative(heading)
        if not narrative or len(narrative) < 20:
            continue
        if re.search(r"\b(?:kg|u|l)\s+\d+\s+\d", narrative, re.IGNORECASE):
            continue
        short = re.sub(r"\s+", " ", narrative).strip(" :")[:90]
        hints.append(f"{heading} ({short})")
        if len(hints) >= 3:
            break
    if hints:
        return [
            "Impossible de departager les sous-positions du TEC sous "
            f"{position_code} : preciser la categorie selon les libelles TEC "
            f"({'; '.join(hints[:3])})"
        ]
    return [
        f"Impossible de departager les sous-positions du TEC sous {position_code} "
        "avec la description fournie."
    ]


def _position_uses_heading_narrative_gate(position_code: str) -> bool:
    """
    True si la position comporte plusieurs sous-positions a 6 chiffres dont la
    discrimination releve du libelle narratif TEC (ex. 8471), et non de criteres
    de surface ou de montage au niveau 8 chiffres seulement.
    """
    headings = _list_distinct_headings(position_code)
    if len(headings) <= 1:
        return False
    if not any(lookup_heading_narrative(heading) for heading in headings):
        return False
    candidates: list[tuple[str, str]] = []
    for heading in headings:
        candidates.extend(_list_subposition_candidates(heading))
    if any(_label_surface_material(label) for _, label in candidates):
        return False
    non_autres = [
        (code, label)
        for code, label in candidates
        if not _label_is_autres_fallback(label) and not _label_requires_mounting_industry(label)
    ]
    return len(non_autres) == 0


def _evaluate_position_headings(
    position_code: str,
    source: str,
) -> tuple[list[str], list[str], list[str]]:
    """
    Evalue les sous-positions a 6 chiffres sous une position.
    Retourne (viables, rejetees, criteres_manquants).
    """
    headings = _list_distinct_headings(position_code)
    if len(headings) <= 1:
        return headings, [], []

    viable: list[str] = []
    rejected: list[str] = []
    unknown: list[str] = []
    for heading in headings:
        discriminants = _heading_discriminant_tokens(heading, position_code)
        if not discriminants:
            unknown.append(heading)
            continue
        if _heading_confirmed_by_source(heading, position_code, source, headings):
            viable.append(heading)
        else:
            source_norm = _normalize(source)
            if any(_token_matches_source(token, source_norm) for token in discriminants):
                unknown.append(heading)
            else:
                rejected.append(heading)

    if len(viable) == 1:
        return viable, rejected, []
    if len(viable) > 1:
        return viable, rejected, _build_heading_missing_criteria(position_code, viable)
    return [], rejected, _build_heading_missing_criteria(position_code, headings)


def _list_position_subposition_candidates(position_code: str) -> list[tuple[str, str]]:
    """Toutes les sous-positions a 8 chiffres sous une position (4 chiffres)."""
    position_digits = re.sub(r"\D", "", position_code or "")
    if len(position_digits) < 4:
        return []
    index = get_tariff_label_index()
    found: list[tuple[str, str]] = []
    for code, label in index.items():
        digits = _hs_digits(code)
        if digits.startswith(position_digits) and len(digits) >= 8:
            found.append((code, label))
    return sorted(found, key=lambda pair: pair[0])


def _list_subposition_candidates(heading: str) -> list[tuple[str, str]]:
    heading_digits = heading.replace(".", "")
    if len(heading_digits) < 6:
        heading_digits = heading_digits.ljust(6, "0")[:6]
    index = get_tariff_label_index()
    found: list[tuple[str, str]] = []
    for code, label in index.items():
        digits = _hs_digits(code)
        if not digits.startswith(heading_digits):
            continue
        if len(digits) < 8:
            continue
        found.append((code, label))
    return sorted(found, key=lambda pair: pair[0])


def _format_hs_code(digits: str) -> str:
    if len(digits) <= 4:
        return f"{digits[:4]}"
    if len(digits) <= 6:
        return f"{digits[:4]}.{digits[4:6]}"
    if len(digits) <= 8:
        return f"{digits[:4]}.{digits[4:6]}.{digits[6:8]}"
    return f"{digits[:4]}.{digits[4:6]}.{digits[6:8]}.{digits[8:10]}"


def _list_immediate_children(parent_code: str) -> list[tuple[str, str]]:
    """Sous-positions directes au niveau inferieur (pas toutes les descendantes)."""
    parent_digits = _hs_digits(parent_code)
    if not parent_digits:
        return []

    index = get_tariff_label_index()
    descendant_depths = [
        len(digits)
        for code in index
        if (digits := _hs_digits(code)).startswith(parent_digits) and len(digits) > len(parent_digits)
    ]

    if len(parent_digits) == 4:
        headings = _list_distinct_headings(parent_code)
        if headings:
            children: list[tuple[str, str]] = []
            for heading in headings:
                narrative = lookup_heading_narrative(heading) or ""
                if narrative:
                    children.append((heading, narrative))
                    continue
                sub_labels = _list_subposition_candidates(heading)
                if sub_labels:
                    children.append((heading, sub_labels[0][1]))
            if children:
                return children

    if not descendant_depths:
        return []

    child_depth = min(descendant_depths)
    grouped: dict[str, str] = {}
    for code, label in index.items():
        digits = _hs_digits(code)
        if not digits.startswith(parent_digits) or len(digits) < child_depth:
            continue
        child_code = _format_hs_code(digits[:child_depth])
        previous = grouped.get(child_code)
        if not previous or len(label) > len(previous):
            grouped[child_code] = label

    return sorted(grouped.items(), key=lambda pair: pair[0])


def _pick_best_leaf_code(parent_code: str) -> str:
    """Code le plus fin indexe sous un noeud confirme."""
    parent_digits = _hs_digits(parent_code)
    index = get_tariff_label_index()
    best_code = parent_code
    best_len = len(parent_digits)
    for code in index:
        digits = _hs_digits(code)
        if digits.startswith(parent_digits) and len(digits) > best_len:
            best_code = code
            best_len = len(digits)
    return best_code


def _has_immediate_children(parent_code: str) -> bool:
    return bool(_list_immediate_children(parent_code))


def _evaluate_heading_level(
    children: list[tuple[str, str]],
    source: str,
    position_code: str,
) -> SubpositionWorkflowResult:
    """Evalue les sous-positions a 6 chiffres via leur libelle narratif TEC."""
    evaluations: list[SubpositionEvaluation] = []
    headings = [code for code, _label in children]
    for code, label in children:
        if _heading_confirmed_by_source(code, position_code, source, headings):
            status = SUBPOSITION_CONFIRMED
        else:
            discriminants = _heading_discriminant_tokens(code, position_code)
            source_norm = _normalize(source)
            if discriminants and not any(
                _token_matches_source(token, source_norm) for token in discriminants
            ):
                status = SUBPOSITION_EXCLUDED
            else:
                status = SUBPOSITION_UNVERIFIABLE
        profile = _candidate_profile(label)
        criteria = (
            [DiscriminantCriterion("narrative", "Libelle narratif TEC", label[:120])]
            if label
            else []
        )
        evaluations.append(
            SubpositionEvaluation(
                code=code,
                label=label,
                status=status,
                criteria=criteria,
                detail=_detail_for_subposition_status(status, profile),
            )
        )
    final_decision = _finalize_subposition_decision(evaluations, children)
    return SubpositionWorkflowResult(
        evaluations=evaluations,
        final_decision=final_decision,
    )


def _evaluate_level(
    parent_code: str,
    children: list[tuple[str, str]],
    source: str,
    *,
    position_code: str,
    trust_identification: bool,
) -> SubpositionWorkflowResult:
    parent_digits = len(_hs_digits(parent_code))
    if parent_digits == 4 and all(len(_hs_digits(code)) == 6 for code, _ in children):
        if all(lookup_heading_narrative(code) for code, _ in children):
            return _evaluate_heading_level(children, source, position_code)
    return _run_subposition_workflow(
        children,
        source,
        trust_identification=trust_identification,
    )


@dataclass
class _HierarchicalResolution:
    stop_code: str
    matched_code: str
    final_decision: FinalSubpositionDecision
    evaluations: list[SubpositionEvaluation]
    studied: list[str]
    excluded: list[str]


def _resolve_hierarchically(
    parent_code: str,
    source: str,
    *,
    position_code: str,
    trust_identification: bool = False,
    evaluations_acc: list[SubpositionEvaluation] | None = None,
    studied_acc: list[str] | None = None,
    excluded_acc: list[str] | None = None,
) -> _HierarchicalResolution:
    """
    Lit le niveau, elimine immediatement les libelles incompatibles,
    confirme si une seule voie reste, puis descend uniquement en dessous.
    """
    evaluations_acc = list(evaluations_acc or [])
    studied_acc = list(studied_acc or [])
    excluded_acc = list(excluded_acc or [])

    children = _list_immediate_children(parent_code)
    if not children:
        leaf = _pick_best_leaf_code(parent_code)
        return _HierarchicalResolution(
            stop_code=parent_code,
            matched_code=leaf,
            final_decision=FinalSubpositionDecision(
                outcome=FINAL_RETAIN_FULL_CODE,
                matched_code=leaf,
                viable=[leaf],
                explanation=_explanation_for_outcome(FINAL_RETAIN_FULL_CODE, leaf),
            ),
            evaluations=evaluations_acc,
            studied=studied_acc,
            excluded=excluded_acc,
        )

    studied_acc.extend(code for code, _ in children)
    level_workflow = _evaluate_level(
        parent_code,
        children,
        source,
        position_code=position_code,
        trust_identification=trust_identification,
    )
    evaluations_acc.extend(level_workflow.evaluations)
    excluded_acc.extend(
        code for code in level_workflow.final_decision.excluded if code not in excluded_acc
    )
    final = level_workflow.final_decision

    if final.outcome in {FINAL_RETAIN_FULL_CODE, FINAL_RETAIN_AUTRES} and final.matched_code:
        confirmed_parent = final.matched_code
        if _has_immediate_children(confirmed_parent):
            deeper = _resolve_hierarchically(
                confirmed_parent,
                source,
                position_code=position_code,
                trust_identification=trust_identification,
                evaluations_acc=evaluations_acc,
                studied_acc=studied_acc,
                excluded_acc=excluded_acc,
            )
            deeper.final_decision = FinalSubpositionDecision(
                outcome=final.outcome,
                matched_code=deeper.matched_code,
                viable=[deeper.matched_code],
                excluded=deeper.excluded,
                missing_notes=[],
                explanation=_explanation_for_outcome(final.outcome, deeper.matched_code),
            )
            return deeper

        leaf = _pick_best_leaf_code(confirmed_parent)
        return _HierarchicalResolution(
            stop_code=parent_code,
            matched_code=leaf,
            final_decision=FinalSubpositionDecision(
                outcome=final.outcome,
                matched_code=leaf,
                viable=[leaf],
                excluded=excluded_acc,
                explanation=_explanation_for_outcome(final.outcome, leaf),
            ),
            evaluations=evaluations_acc,
            studied=studied_acc,
            excluded=excluded_acc,
        )

    return _HierarchicalResolution(
        stop_code=parent_code,
        matched_code="",
        final_decision=final,
        evaluations=evaluations_acc,
        studied=studied_acc,
        excluded=excluded_acc,
    )


def _list_subposition_candidates_for_hs(hs_code: str) -> tuple[str, list[tuple[str, str]]]:
    """Candidats sous la sous-position retenue, ou sous la position (4 ch.) si besoin."""
    heading = _heading_code(hs_code)
    candidates = _list_subposition_candidates(heading)
    if candidates:
        return heading, candidates

    position = position_code_from_hs(hs_code)
    wider = _list_position_subposition_candidates(position)
    return heading, wider


def position_has_discriminating_subpositions(hs_code: str) -> bool:
    """True si le TEC indexe des sous-positions avec criteres de subdivision sous cette position."""
    _, candidates = _list_subposition_candidates_for_hs(hs_code)
    return bool(candidates)


def _consolidate_missing_criteria(
    missing_notes: list[str],
    candidates: list[tuple[str, str]],
) -> list[str]:
    """Regroupe les manques par critere juridiquement discriminant (pas de demandes generiques)."""
    if not missing_notes:
        return []

    surface_materials: set[str] = set()
    mounting_needed = False
    token_notes: list[str] = []

    for note in missing_notes:
        norm = _normalize(note)
        if "surface exterieure en" in norm:
            match = re.search(r"surface exterieure en ([^(]+)", norm)
            if match:
                surface_materials.add(match.group(1).strip())
        elif "etat de presentation" in norm:
            mounting_needed = True
        else:
            token_notes.append(note)

    consolidated: list[str] = []
    if surface_materials:
        surface_codes = sorted(
            {
                code
                for code, label in candidates
                if (
                    _label_surface_material(label)
                    and _normalize(_label_surface_material(label) or "") in surface_materials
                )
                or any(mat in _normalize(label) for mat in surface_materials)
            }
        )
        materials = ", ".join(sorted(surface_materials))
        if len(surface_materials) == 1:
            code_hint = surface_codes[0] if surface_codes else "TEC"
            consolidated.append(
                f"Surface exterieure en {materials} (critere discriminant du libelle TEC {code_hint})"
            )
        else:
            consolidated.append(
                f"Surface exterieure (matiere apparente) : preciser parmi {materials} "
                "(criteres discriminants TEC)"
            )
    if mounting_needed:
        consolidated.append(
            "Etat de presentation : monte ou demonte/non monte pour l'industrie du montage "
            "(critere discriminant TEC)"
        )

    seen: set[str] = set()
    for note in token_notes:
        key = note[:100]
        if key not in seen:
            seen.add(key)
            consolidated.append(note)

    return consolidated[:6]


def _build_criteria_trace(
    evaluations: list[SubpositionEvaluation],
    missing_notes: list[str],
) -> list[dict[str, str]]:
    """Trace du workflow : criteres extraits, comparaison, statut par sous-position."""
    trace: list[dict[str, str]] = []
    missing_blob = " ".join(missing_notes)

    for evaluation in evaluations:
        if _label_is_autres_fallback(evaluation.label):
            if evaluation.status != SUBPOSITION_UNVERIFIABLE:
                pass
            elif evaluation.code not in missing_blob and not any(
                evaluation.code in note for note in missing_notes
            ):
                continue

        clean_label = re.sub(r"^-+\s*", "", evaluation.label).strip()
        if not clean_label:
            continue

        if evaluation.status == SUBPOSITION_UNVERIFIABLE:
            if evaluation.code not in missing_blob and not any(
                evaluation.code in note for note in missing_notes
            ):
                if not evaluation.criteria:
                    continue

        detail = evaluation.detail
        if evaluation.status == SUBPOSITION_UNVERIFIABLE and missing_notes:
            detail = next(
                (note for note in missing_notes if evaluation.code in note),
                evaluation.detail,
            )

        trace.append(
            {
                "criterion_id": evaluation.code,
                "label": clean_label,
                "status": evaluation.status,
                "tec_reference": evaluation.code,
                "detail": detail[:240],
            }
        )

    return trace


def build_criteria_trace_from_tec(
    hs_code: str,
    source_text: str,
    *,
    trust_identification: bool = False,
) -> list[dict[str, str]]:
    """Expose la trace des criteres TEC pour un code et une description."""
    workflow = run_subposition_workflow(
        hs_code,
        source_text or "",
        trust_identification=trust_identification,
    )
    return _build_criteria_trace(workflow.evaluations, workflow.missing_notes)


def _position_wide_single_match(
    position: str,
    source: str,
    *,
    trust_identification: bool = False,
) -> str | None:
    """Retourne le code a 8 chiffres unique si les criteres resolus ne laissent qu'une voie."""
    candidates = _list_position_subposition_candidates(position)
    if len(candidates) <= 1:
        return None
    viable, _rejected, missing_notes = _evaluate_subposition_candidates(
        candidates,
        source,
        trust_identification=trust_identification,
    )
    if len(viable) == 1 and not missing_notes:
        return viable[0]
    return None


def _confirmed_subdivision_result(
    matched: str,
    heading: str,
    *,
    studied: list[str],
    rejected: list[str],
    criteria_trace: list[dict[str, str]],
    subposition_evaluations: list[dict[str, Any]] | None = None,
    final_decision: dict[str, Any] | None = None,
    explanation: str | None = None,
) -> SubdivisionResult:
    resolved_final = final_decision or FinalSubpositionDecision(
        outcome=FINAL_RETAIN_FULL_CODE,
        matched_code=matched,
        viable=[matched],
        excluded=rejected,
        explanation=explanation or _explanation_for_outcome(FINAL_RETAIN_FULL_CODE, matched),
    ).to_dict()
    return SubdivisionResult(
        status="confirmed",
        hs_code=matched,
        heading_code=heading,
        matched_code=matched,
        candidates_studied=studied,
        rejected_codes=rejected,
        criteria_trace=criteria_trace,
        subposition_evaluations=subposition_evaluations or [],
        final_decision=resolved_final,
        confidence_cap=_confidence_cap_for_digits(len(_hs_digits(matched))),
        explanation=explanation or str(resolved_final.get("explanation") or ""),
    )


def _workflow_artifacts(
    workflow: SubpositionWorkflowResult,
    candidates: list[tuple[str, str]],
) -> tuple[FinalSubpositionDecision, list[str], list[dict[str, str]], list[dict[str, Any]]]:
    missing_criteria = _consolidate_missing_criteria(
        workflow.final_decision.missing_notes,
        candidates,
    )
    criteria_trace = _build_criteria_trace(workflow.evaluations, workflow.final_decision.missing_notes)
    subposition_evaluations = [evaluation.to_dict() for evaluation in workflow.evaluations]
    return workflow.final_decision, missing_criteria, criteria_trace, subposition_evaluations


def _subdivision_result_from_workflow(
    heading: str,
    studied: list[str],
    workflow: SubpositionWorkflowResult,
    candidates: list[tuple[str, str]],
) -> SubdivisionResult:
    final, missing_criteria, criteria_trace, subposition_evaluations = _workflow_artifacts(
        workflow,
        candidates,
    )

    if final.outcome in {FINAL_RETAIN_FULL_CODE, FINAL_RETAIN_AUTRES}:
        return _confirmed_subdivision_result(
            final.matched_code,
            heading,
            studied=studied,
            rejected=final.excluded,
            criteria_trace=criteria_trace,
            subposition_evaluations=subposition_evaluations,
            final_decision=final.to_dict(),
            explanation=final.explanation,
        )

    if final.outcome == FINAL_INCOHERENT:
        return SubdivisionResult(
            status="incoherent",
            hs_code=heading,
            heading_code=heading,
            candidates_studied=studied,
            rejected_codes=final.excluded,
            missing_criteria=[],
            criteria_trace=criteria_trace,
            subposition_evaluations=subposition_evaluations,
            final_decision=final.to_dict(),
            confidence_cap=_confidence_cap_for_digits(len(_hs_digits(heading))),
            explanation=final.explanation,
        )

    status = final.subdivision_status
    confidence_cap = (
        70
        if status == "ambiguous"
        else _confidence_cap_for_digits(len(_hs_digits(heading)))
    )
    return SubdivisionResult(
        status=status,
        hs_code=heading,
        heading_code=heading,
        candidates_studied=studied,
        rejected_codes=final.excluded,
        missing_criteria=missing_criteria,
        criteria_trace=criteria_trace,
        subposition_evaluations=subposition_evaluations,
        final_decision=final.to_dict(),
        confidence_cap=confidence_cap,
        explanation=final.explanation,
    )


def _autres_codes(candidates: list[tuple[str, str]]) -> list[str]:
    return [code for code, label in candidates if _label_is_autres_fallback(label)]


def _non_autres_codes(candidates: list[tuple[str, str]]) -> list[str]:
    return [code for code, label in candidates if not _label_is_autres_fallback(label)]


def _outcome_for_single_match(
    matched_code: str,
    excluded: list[str],
    candidates: list[tuple[str, str]],
) -> str:
    autres = _autres_codes(candidates)
    non_autres = _non_autres_codes(candidates)
    if (
        matched_code in autres
        and non_autres
        and all(code in excluded for code in non_autres)
    ):
        return FINAL_RETAIN_AUTRES
    return FINAL_RETAIN_FULL_CODE


def _explanation_for_outcome(outcome: str, matched_code: str = "") -> str:
    if outcome == FINAL_RETAIN_FULL_CODE:
        return (
            "Une seule sous-position confirmee apres verification des criteres discriminants "
            f"du TEC ; code complet retenu ({matched_code})."
            if matched_code
            else "Une seule sous-position confirmee ; code complet retenu."
        )
    if outcome == FINAL_RETAIN_AUTRES:
        return (
            "Toutes les sous-positions specifiques sont exclues ; sous-position residuelle "
            f"« Autres » retenue ({matched_code})."
            if matched_code
            else "Toutes les sous-positions specifiques sont exclues ; sous-position « Autres » retenue."
        )
    if outcome == FINAL_STOP_INSUFFICIENT:
        return (
            "Plusieurs sous-positions restent juridiquement possibles faute de criteres "
            "discriminants suffisants : arret au dernier niveau certain."
        )
    return (
        "Incoherence entre la description de la marchandise et les sous-positions du TEC : "
        "aucune sous-position compatible."
    )


def _finalize_subposition_decision(
    evaluations: list[SubpositionEvaluation],
    candidates: list[tuple[str, str]],
) -> FinalSubpositionDecision:
    """Analyse finale : departage puis decision parmi les quatre issues possibles."""
    evaluated = [
        (evaluation.code, evaluation.label, evaluation.status, _candidate_profile(evaluation.label))
        for evaluation in evaluations
    ]

    confirmed = [
        code for code, _label, state, _profile in evaluated if state == SUBPOSITION_CONFIRMED
    ]
    excluded = [
        code for code, _label, state, _profile in evaluated if state == SUBPOSITION_EXCLUDED
    ]
    unverifiable = [
        (code, label, profile)
        for code, label, state, profile in evaluated
        if state == SUBPOSITION_UNVERIFIABLE
    ]

    autres_unverifiable = [
        (code, label, profile) for code, label, profile in unverifiable if profile.is_autres
    ]
    non_autres_unverifiable = [
        (code, label, profile) for code, label, profile in unverifiable if not profile.is_autres
    ]
    non_autres_excluded = bool(_non_autres_codes(candidates)) and all(
        state == SUBPOSITION_EXCLUDED
        for code, _label, state, profile in evaluated
        if not profile.is_autres
    )

    def _decision(
        outcome: str,
        *,
        matched_code: str = "",
        viable: list[str] | None = None,
        missing_notes: list[str] | None = None,
        explanation: str = "",
    ) -> FinalSubpositionDecision:
        resolved_viable = list(viable or ([matched_code] if matched_code else []))
        return FinalSubpositionDecision(
            outcome=outcome,
            matched_code=matched_code,
            viable=resolved_viable,
            excluded=excluded,
            missing_notes=missing_notes or [],
            explanation=explanation or _explanation_for_outcome(outcome, matched_code),
        )

    if confirmed:
        viable = list(dict.fromkeys(confirmed))
        autres_codes = _autres_codes(candidates)
        if len(viable) > 1 and autres_codes:
            non_autres = [code for code in viable if code not in autres_codes]
            if len(non_autres) == 1:
                viable = non_autres
        if len(viable) > 1:
            confirmed_profiles = [
                _candidate_profile(label)
                for code, label in candidates
                if code in viable
            ]
            discriminant_keys = {_profile_discriminant_key(profile) for profile in confirmed_profiles}
            label_signatures = {profile.signature for profile in confirmed_profiles if profile.signature}
            if len(discriminant_keys) == 1 or (len(label_signatures) == 1 and label_signatures):
                matched = viable[0]
                outcome = _outcome_for_single_match(matched, excluded, candidates)
                return _decision(outcome, matched_code=matched, viable=[matched])
        if len(viable) == 1:
            matched = viable[0]
            outcome = _outcome_for_single_match(matched, excluded, candidates)
            return _decision(outcome, matched_code=matched, viable=[matched])
        missing_notes = _build_missing_notes_for_unverifiable(
            [(code, label, _candidate_profile(label)) for code, label in candidates if code in viable],
            candidates,
        )
        return _decision(
            FINAL_STOP_INSUFFICIENT,
            viable=viable,
            missing_notes=missing_notes,
        )

    if non_autres_unverifiable and non_autres_excluded and autres_unverifiable:
        matched = autres_unverifiable[0][0]
        return _decision(FINAL_RETAIN_AUTRES, matched_code=matched, viable=[matched])

    if len(unverifiable) == 1:
        matched = unverifiable[0][0]
        outcome = _outcome_for_single_match(matched, excluded, candidates)
        return _decision(outcome, matched_code=matched, viable=[matched])

    autres_only = [
        (code, label, profile) for code, label, profile in unverifiable if profile.is_autres
    ]
    non_autres_only = [
        (code, label, profile) for code, label, profile in unverifiable if not profile.is_autres
    ]

    if unverifiable:
        if autres_only and non_autres_only:
            missing_notes = _build_missing_notes_for_unverifiable(unverifiable, candidates)
            if missing_notes:
                return _decision(
                    FINAL_STOP_INSUFFICIENT,
                    missing_notes=missing_notes,
                )
            return _decision(
                FINAL_STOP_INSUFFICIENT,
                missing_notes=[
                    "Impossible de departager les sous-positions TEC avec la description fournie."
                ],
            )

        target = non_autres_only or unverifiable
        discriminant_keys = {_profile_discriminant_key(profile) for _code, _label, profile in target}
        label_signatures = {profile.signature for _code, _label, profile in target if profile.signature}
        if len(discriminant_keys) == 1 or (len(label_signatures) == 1 and label_signatures):
            matched = target[0][0]
            outcome = _outcome_for_single_match(matched, excluded, candidates)
            return _decision(outcome, matched_code=matched, viable=[matched])

        missing_notes = _build_missing_notes_for_unverifiable(unverifiable, candidates)
        if missing_notes:
            return _decision(FINAL_STOP_INSUFFICIENT, missing_notes=missing_notes)
        matched = target[0][0]
        outcome = _outcome_for_single_match(matched, excluded, candidates)
        return _decision(outcome, matched_code=matched, viable=[matched])

    if autres_unverifiable and non_autres_excluded:
        matched = autres_unverifiable[0][0]
        return _decision(FINAL_RETAIN_AUTRES, matched_code=matched, viable=[matched])

    if excluded and len(excluded) == len(candidates):
        return _decision(FINAL_INCOHERENT)

    if excluded and not unverifiable and not confirmed:
        return _decision(FINAL_INCOHERENT)

    return _decision(FINAL_STOP_INSUFFICIENT)


def _run_subposition_workflow(
    candidates: list[tuple[str, str]],
    source: str,
    *,
    trust_identification: bool = False,
) -> SubpositionWorkflowResult:
    evaluations = [
        _evaluate_single_subposition(
            code,
            label,
            source,
            trust_identification=trust_identification,
        )
        for code, label in candidates
    ]
    final_decision = _finalize_subposition_decision(evaluations, candidates)
    return SubpositionWorkflowResult(
        evaluations=evaluations,
        final_decision=final_decision,
    )


def run_subposition_workflow(
    hs_code: str,
    source_text: str,
    *,
    trust_identification: bool = False,
) -> SubpositionWorkflowResult:
    """Execute le workflow complet de sous-position pour une position retenue."""
    _, candidates = _list_subposition_candidates_for_hs(hs_code)
    if not candidates:
        return SubpositionWorkflowResult(
            evaluations=[],
            final_decision=FinalSubpositionDecision(
                outcome=FINAL_STOP_INSUFFICIENT,
                explanation="Aucune sous-position indexee sous cette position dans le TEC.",
            ),
        )
    return _run_subposition_workflow(
        candidates,
        source_text or "",
        trust_identification=trust_identification,
    )


def _evaluate_subposition_candidates(
    candidates: list[tuple[str, str]],
    source: str,
    *,
    trust_identification: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """
    Retourne (viable, rejected, missing_notes brutes).
    Les criteres manquants ne sont emis que s'ils departagent encore plusieurs candidats.
    """
    workflow = _run_subposition_workflow(
        candidates,
        source,
        trust_identification=trust_identification,
    )
    return workflow.viable, workflow.excluded, workflow.missing_notes


def preview_missing_discriminating_criteria(
    hs_code: str,
    source_text: str,
    item: dict[str, Any] | None = None,
) -> list[str]:
    """
    Retourne uniquement les informations juridiquement necessaires et discriminantes
    pour la position retenue, d'apres le TEC. Liste vide si la sous-position est resolvable.
    """
    from .classification_source import build_effective_classification_source

    effective_source, trusted = build_effective_classification_source(source_text, item)
    result = resolve_subposition_from_tec(
        hs_code,
        effective_source,
        trust_identification=trusted,
    )
    if result.status == "confirmed":
        return []
    return list(result.missing_criteria)


@dataclass
class SubdivisionResult:
    status: str  # confirmed | ambiguous | insufficient | incoherent
    hs_code: str
    heading_code: str
    matched_code: str = ""
    missing_criteria: list[str] = field(default_factory=list)
    candidates_studied: list[str] = field(default_factory=list)
    rejected_codes: list[str] = field(default_factory=list)
    confidence_cap: int = 95
    explanation: str = ""
    criteria_trace: list[dict[str, str]] = field(default_factory=list)
    subposition_evaluations: list[dict[str, Any]] = field(default_factory=list)
    final_decision: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "hs_code": self.hs_code,
            "heading_code": self.heading_code,
            "matched_code": self.matched_code,
            "missing_criteria": self.missing_criteria,
            "candidates_studied": self.candidates_studied,
            "rejected_codes": self.rejected_codes,
            "confidence_cap": self.confidence_cap,
            "explanation": self.explanation,
            "criteria_trace": self.criteria_trace,
            "subposition_evaluations": self.subposition_evaluations,
            "final_decision": self.final_decision,
        }


def resolve_subposition_from_tec(
    hs_code: str,
    source_text: str,
    *,
    trust_identification: bool = False,
) -> SubdivisionResult:
    """
    Resolution hierarchique TEC : a chaque niveau, elimination immediate des libelles
    incompatibles, confirmation si une seule voie reste, descente uniquement ensuite.
    """
    source = source_text or ""
    position = position_code_from_hs(hs_code)
    digits = _hs_digits(hs_code)
    if len(digits) <= 4:
        start_parent = position
    elif len(digits) <= 6:
        start_parent = f"{digits[:4]}.{digits[4:6]}"
    else:
        start_parent = _heading_code(hs_code)

    if not _list_immediate_children(start_parent):
        if len(digits) > 4 and start_parent != position and _list_immediate_children(position):
            start_parent = position

    if not _list_immediate_children(start_parent):
        indexed_label = lookup_position_label(hs_code)
        heading = _heading_code(hs_code)
        if len(digits) >= 8 and indexed_label:
            return SubdivisionResult(
                status="confirmed",
                hs_code=hs_code,
                heading_code=heading,
                matched_code=hs_code,
                confidence_cap=_confidence_cap_for_digits(len(digits)),
                explanation="Code deja present dans le referentiel TEC indexe.",
                final_decision=FinalSubpositionDecision(
                    outcome=FINAL_RETAIN_FULL_CODE,
                    matched_code=hs_code,
                    viable=[hs_code],
                    explanation="Code deja present dans le referentiel TEC indexe.",
                ).to_dict(),
            )
        return SubdivisionResult(
            status="insufficient",
            hs_code=heading,
            heading_code=heading,
            confidence_cap=_confidence_cap_for_digits(min(len(digits), 6)),
            explanation=(
                "Aucune sous-position indexee sous cette position dans le TEC : "
                "arret au dernier niveau justifiable."
            ),
        )

    resolution = _resolve_hierarchically(
        start_parent,
        source,
        position_code=position,
        trust_identification=trust_identification,
    )
    workflow = SubpositionWorkflowResult(
        evaluations=resolution.evaluations,
        final_decision=resolution.final_decision,
    )
    candidates = [(evaluation.code, evaluation.label) for evaluation in resolution.evaluations]
    studied = list(dict.fromkeys(resolution.studied))
    return _subdivision_result_from_workflow(
        resolution.stop_code,
        studied,
        workflow,
        candidates,
    )


def _confidence_cap_for_digits(digit_count: int) -> int:
    if digit_count >= 10:
        return 95
    if digit_count >= 8:
        return 85
    if digit_count >= 6:
        return 75
    if digit_count >= 4:
        return 65
    return 55


def apply_subposition_resolution(item: dict[str, Any], source_text: str | None = None) -> SubdivisionResult:
    """Applique la resolution TEC sur un item de classification."""
    from .classification_source import build_effective_classification_source

    raw_source = (source_text or str(item.get("source_query") or item.get("description") or "")).strip()
    source, trusted = build_effective_classification_source(raw_source, item)
    hs = str(item.get("hs_code") or "").strip()
    if not hs or not source:
        result = SubdivisionResult(
            status="insufficient",
            hs_code=hs,
            heading_code=_heading_code(hs),
            confidence_cap=55,
            explanation="Code ou description source manquant.",
        )
        item["subposition_resolution"] = result.to_dict()
        return result

    result = resolve_subposition_from_tec(hs, source, trust_identification=trusted)
    item["subposition_resolution"] = result.to_dict()

    if result.status == "confirmed":
        item["hs_code"] = result.matched_code or result.hs_code
        label = lookup_position_label(result.matched_code)
        if label:
            item["position_label"] = label
        item.pop("subposition_status", None)
        item.pop("subposition_label", None)
    else:
        stop_code = str(result.hs_code or result.heading_code or hs).strip()
        item["hs_code"] = stop_code
        if result.missing_criteria:
            item["subposition_status"] = "a_determiner"
            item["subposition_label"] = f"Sous-position a determiner : {result.missing_criteria[0]}"
        else:
            item.pop("subposition_status", None)
            item.pop("subposition_label", None)
        heading_label = lookup_position_label(stop_code) or get_position_heading(stop_code)
        if heading_label:
            item["position_label"] = heading_label

    try:
        current = int(item.get("confidence") or 0)
    except (TypeError, ValueError):
        current = 90
    if result.status == "confirmed":
        item["confidence"] = max(current, result.confidence_cap)
    else:
        item["confidence"] = min(current or result.confidence_cap, result.confidence_cap)

    if result.status != "confirmed" and result.missing_criteria:
        item["classification_status"] = "provisoire"
    elif result.status == "incoherent":
        item["classification_status"] = "provisoire"
        item["subposition_status"] = "incoherent"
        item["subposition_label"] = result.explanation
    return result
