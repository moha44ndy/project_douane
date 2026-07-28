"""Typed, tariff-neutral product evidence shared by retrieval and classification."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .functional_profile import FunctionalProfile


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(item) for item in value if _clean(item)]


def _source_urls(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    urls: list[str] = []
    for item in value:
        if isinstance(item, dict):
            url = _clean(item.get("url"))
        else:
            url = _clean(item)
        if url and url not in urls:
            urls.append(url)
    return urls[:10]


@dataclass(frozen=True)
class ProductEvidence:
    """Facts about a product before any customs position is selected."""

    source_text: str = ""
    input_type: str = "free_description"
    identification_status: str = "provided"
    designation: str = ""
    manufacturer: str = ""
    manufacturer_reference: str = ""
    commercial_name: str = ""
    technical_nature: str = ""
    technical_nature_confidence: int = 0
    technical_nature_signals: list[str] = field(default_factory=list)
    family: str = ""
    primary_function: str = ""
    system_role: str = "unspecified"
    composition: str = ""
    characteristics: list[str] = field(default_factory=list)
    identity_terms: list[str] = field(default_factory=list)
    semantic_terms: list[str] = field(default_factory=list)
    ambiguity_flags: list[str] = field(default_factory=list)
    missing_discriminants: list[str] = field(default_factory=list)
    evidence_sources: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    identity_confidence: int = 0
    evidence_completeness: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def retrieval_query(self) -> str:
        """Compact functional query without logistics, prices or tariff guesses."""
        identity_block = ""
        if self.input_type == "manufacturer_ref" or self.identity_confidence >= 70:
            identity_block = " ".join(self.identity_terms)
        parts = [
            identity_block,
            self.technical_nature,
            self.primary_function,
            self.system_role if self.system_role != "unspecified" else "",
            " ".join(self.characteristics),
            self.composition,
            self.family,
            " ".join(self.semantic_terms),
        ]
        return _clean(" ".join(part for part in parts if part))[:1100]

    def prompt_block(self) -> str:
        lines = ["PREUVES PRODUIT STRUCTUREES (sans decision tarifaire) :"]
        if self.designation:
            lines.append(f"Designation source : {self.designation}")
        if self.manufacturer:
            lines.append(f"Fabricant : {self.manufacturer}")
        if self.commercial_name:
            lines.append(f"Nom commercial : {self.commercial_name}")
        if self.manufacturer_reference:
            lines.append(f"Reference fabricant : {self.manufacturer_reference}")
        if self.technical_nature:
            lines.append(f"Nature technique : {self.technical_nature}")
            lines.append(
                f"Confiance nature technique : {self.technical_nature_confidence}%"
            )
        if self.primary_function:
            lines.append(f"Fonction principale : {self.primary_function}")
        if self.system_role != "unspecified":
            lines.append(f"Role dans le systeme : {self.system_role}")
        if self.characteristics:
            lines.append(f"Caracteristiques : {'; '.join(self.characteristics)}")
        if self.composition:
            lines.append(f"Composition : {self.composition}")
        if self.identity_terms:
            lines.append(f"Signaux d'identite : {', '.join(self.identity_terms)}")
        lines.append(
            f"Statut identification : {self.identification_status}; "
            f"confiance identite : {self.identity_confidence}%; "
            f"completude preuves : {self.evidence_completeness}%"
        )
        if self.ambiguity_flags:
            lines.append(
                "Points d'ambiguite : " + "; ".join(self.ambiguity_flags)
            )
        if self.missing_discriminants:
            lines.append(
                "Informations discriminantes manquantes : "
                + "; ".join(self.missing_discriminants)
            )
        lines.append(
            "Choisir une position uniquement si sa fonction et son role sont compatibles "
            "avec ces preuves; sinon conserver un resultat provisoire."
        )
        return "\n".join(lines)


def _identity_terms(
    *,
    manufacturer: str,
    manufacturer_reference: str,
    commercial_name: str,
    designation: str,
    input_type: str,
    confidence: int,
) -> list[str]:
    terms: list[str] = []
    for value in (
        manufacturer,
        commercial_name,
        manufacturer_reference,
    ):
        cleaned = _clean(value)
        if cleaned and cleaned not in terms:
            terms.append(cleaned)
    if input_type == "manufacturer_ref" and designation:
        short_designation = _clean(designation)
        if short_designation and short_designation not in terms:
            terms.append(short_designation)
    if confidence >= 80:
        return terms[:6]
    return terms[:3]


def _ambiguity_flags(
    *,
    input_type: str,
    status: str,
    identity_confidence: int,
    technical_nature_confidence: int,
    manufacturer: str,
    commercial_name: str,
    system_role: str,
    missing_discriminants: list[str],
) -> list[str]:
    flags: list[str] = []
    if status == "uncertain":
        flags.append("identification incertaine")
    if identity_confidence < 60:
        flags.append("identite faible")
    if technical_nature_confidence < 60:
        flags.append("nature technique faible")
    if input_type == "manufacturer_ref" and not (manufacturer or commercial_name):
        flags.append("reference fabricant non rattachee a un produit confirme")
    if system_role == "unspecified":
        flags.append("role systeme non determine")
    if len(missing_discriminants) >= 2:
        flags.append("plusieurs discriminants manquants")
    return flags


def build_product_evidence(
    source_text: str,
    identification: dict[str, Any] | None,
    functional_profile: FunctionalProfile,
) -> ProductEvidence:
    identified = identification if isinstance(identification, dict) else {}
    skipped = bool(identified.get("skipped"))
    unstable = bool(identified.get("identification_unstable"))

    if unstable:
        status = "uncertain"
    elif skipped:
        status = "provided"
    else:
        status = "identified"

    manufacturer_reference = _clean(
        identified.get("manufacturer_part_number")
        or functional_profile.manufacturer_reference
    )
    characteristics = _string_list(identified.get("technical_characteristics"))
    if not characteristics and functional_profile.characteristics:
        characteristics = [functional_profile.characteristics]

    evidence_sources = list(functional_profile.evidence_sources)
    if identified.get("web_search_used") and "web_search" not in evidence_sources:
        evidence_sources.append("web_search")

    confidence = int(identified.get("identification_confidence") or 0)
    if skipped and functional_profile.designation:
        confidence = max(confidence, 100)
    confidence = max(0, min(100, confidence))
    input_type = _clean(identified.get("input_type")) or "free_description"
    if functional_profile.manufacturer_reference:
        input_type = "manufacturer_ref"
    identity_terms = _identity_terms(
        manufacturer=_clean(identified.get("manufacturer")),
        manufacturer_reference=manufacturer_reference,
        commercial_name=_clean(identified.get("commercial_name")),
        designation=functional_profile.designation,
        input_type=input_type,
        confidence=confidence,
    )

    completeness_signals = [
        bool(functional_profile.designation),
        bool(functional_profile.product_type),
        bool(functional_profile.primary_function),
        bool(characteristics),
        bool(functional_profile.composition),
        bool(identity_terms),
    ]
    completeness = round(100 * sum(completeness_signals) / len(completeness_signals))
    ambiguity_flags = _ambiguity_flags(
        input_type=input_type,
        status=status,
        identity_confidence=confidence,
        technical_nature_confidence=functional_profile.technical_nature_confidence,
        manufacturer=_clean(identified.get("manufacturer")),
        commercial_name=_clean(identified.get("commercial_name")),
        system_role=functional_profile.system_role,
        missing_discriminants=list(functional_profile.missing_discriminants),
    )

    return ProductEvidence(
        source_text=str(source_text or "").strip(),
        input_type=input_type,
        identification_status=status,
        designation=functional_profile.designation,
        manufacturer=_clean(identified.get("manufacturer")),
        manufacturer_reference=manufacturer_reference,
        commercial_name=_clean(identified.get("commercial_name")),
        technical_nature=functional_profile.product_type,
        technical_nature_confidence=functional_profile.technical_nature_confidence,
        technical_nature_signals=list(functional_profile.technical_nature_signals),
        family=functional_profile.family,
        primary_function=functional_profile.primary_function,
        system_role=functional_profile.system_role,
        composition=functional_profile.composition,
        characteristics=characteristics,
        identity_terms=identity_terms,
        semantic_terms=list(functional_profile.semantic_terms),
        ambiguity_flags=ambiguity_flags,
        missing_discriminants=list(functional_profile.missing_discriminants),
        evidence_sources=evidence_sources,
        source_urls=_source_urls(identified.get("web_sources")),
        identity_confidence=confidence,
        evidence_completeness=completeness,
    )
