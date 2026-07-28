"""Tariff-neutral functional profile built from user and identification evidence."""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

from openai import OpenAI

from .config.settings import Config
from .openai_compat import chat_completion_kwargs
from .technical_nature import TechnicalNature, infer_technical_nature
from .telemetry import increment_telemetry, record_telemetry_call

logger = logging.getLogger(__name__)
_client = OpenAI(api_key=Config.OPENAI_API_KEY) if Config.OPENAI_API_KEY else None


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


_SECTION_NAMES = {
    "produit": "designation",
    "marchandise": "designation",
    "article": "designation",
    "designation": "designation",
    "reference fabricant": "manufacturer_reference",
    "manufacturer reference": "manufacturer_reference",
    "part number": "manufacturer_reference",
    "mpn": "manufacturer_reference",
    "composition": "composition",
    "matiere": "composition",
    "matiere composition": "composition",
    "materiau": "composition",
    "usage": "primary_function",
    "utilisation": "primary_function",
    "fonction": "primary_function",
    "caracteristiques": "characteristics",
    "caracteristique": "characteristics",
    "specifications": "characteristics",
    "specification": "characteristics",
    "capacite": "characteristics",
}

_FUNCTIONAL_VOCABULARY: tuple[tuple[set[str], set[str]], ...] = (
    (
        {"switch", "switching", "commutateur", "commutation", "router", "routeur", "ethernet"},
        {"network", "reseau", "data", "donnees", "switching", "commutation", "transmission", "reception"},
    ),
    (
        {"camera", "imagerie", "image", "images", "multispectral"},
        {
            "camera", "digital", "numerique", "video", "television", "imaging",
            "imagerie", "image", "optical", "optique", "photographic", "thermique",
        },
    ),
    (
        {"optique", "optical"},
        {"optical", "optique"},
    ),
    (
        {"storage", "stockage", "nas", "baie"},
        {"storage", "stockage", "data", "donnees", "memory", "memoire", "system", "systeme", "unit", "unite"},
    ),
    (
        {"plc", "automate", "automatisme", "controller", "controleur"},
        {"industrial", "industriel", "control", "controle", "commande", "programmable", "process"},
    ),
    (
        {"robot", "robotique", "robotise", "robotisee"},
        {"robot", "industrial", "industriel", "handling", "manutention", "production"},
    ),
    (
        {"variateur", "inverter", "vfd", "convertisseur", "drive"},
        {"converter", "convertisseur", "static", "statique", "electrical", "electrique", "power", "puissance", "motor", "moteur"},
    ),
    (
        {"tablet", "tablette"},
        {
            "tablet", "tablette", "computer", "ordinateur", "portable", "data",
            "donnees", "processing", "traitement", "information", "input", "output",
        },
    ),
    (
        {"headset", "casque", "wearable", "immersive"},
        {
            "headset", "casque", "display", "affichage", "monitor", "moniteur",
            "visual", "optical", "optique", "wearable", "immersive",
        },
    ),
)

_LOW_CONFIDENCE_NATURES = {
    "unspecified product",
    "solid state or magnetic data storage device",
    "server automatic data processing machine",
}


def _parse_sections(source_text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    active_key = ""
    for raw_line in str(source_text or "").replace("\r", "\n").split("\n"):
        line = re.sub(r"^\s*[-*]+\s*", "", raw_line).strip()
        if not line:
            continue
        header = re.match(r"^([^:]{2,40})\s*:\s*(.*)$", line)
        if header:
            key = _SECTION_NAMES.get(_normalize(header.group(1)))
            if key:
                active_key = key
                value = header.group(2).strip()
                if value:
                    sections.setdefault(key, []).append(value)
                continue
            active_key = ""
        if active_key:
            sections.setdefault(active_key, []).append(line)
    return {
        key: re.sub(r"\s+", " ", " ".join(values)).strip()
        for key, values in sections.items()
        if values
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _llm_fallback_enabled() -> bool:
    return bool(
        _client
        and Config.MOSAM_TECHNICAL_NATURE_LLM_FALLBACK_ENABLED
        and Config.OPENAI_API_KEY
    )


def _llm_fallback_model() -> str:
    return (
        (Config.MOSAM_CLASSIFICATION_MODEL_CHEAP or "").strip()
        or (Config.MOSAM_IDENTIFICATION_MODEL or "").strip()
        or (Config.MOSAM_MODEL or "").strip()
        or "gpt-4.1-mini"
    )


def _llm_fallback_threshold() -> int:
    return max(0, min(100, _safe_int(
        Config.MOSAM_TECHNICAL_NATURE_LLM_CONFIDENCE_THRESHOLD,
        55,
    )))


def _looks_like_reference(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if re.search(r"[A-Za-z]", text) and re.search(r"\d", text):
        return bool(re.search(r"[-_./]", text) or " " not in text)
    return False


def _needs_llm_profile_fallback(
    *,
    sections: dict[str, str],
    identification: dict[str, Any],
    inferred_nature: TechnicalNature,
    product_type: str,
    primary_function: str,
    characteristics: str,
) -> bool:
    if not _llm_fallback_enabled():
        return False
    if bool(identification.get("skipped")) is False:
        if product_type and primary_function and (
            identification.get("family") or identification.get("technical_characteristics")
        ):
            return False
        if _safe_int(identification.get("identification_confidence"), 0) >= 70:
            return False
    if inferred_nature.confidence >= _llm_fallback_threshold() and product_type not in _LOW_CONFIDENCE_NATURES:
        return False
    manufacturer_reference = sections.get("manufacturer_reference", "")
    designation = sections.get("designation", "")
    detail_strength = len(_normalize(" ".join([primary_function, characteristics])).split())
    has_reference_signal = _looks_like_reference(manufacturer_reference) or _looks_like_reference(designation)
    if not has_reference_signal and detail_strength < 5:
        return False
    source_signals = " ".join(
        filter(
            None,
            [
                designation,
                manufacturer_reference,
                product_type,
                primary_function,
                characteristics,
                sections.get("composition", ""),
            ],
        )
    )
    words = _normalize(source_signals).split()
    if len(words) < 4:
        return False
    if not primary_function and not characteristics and not manufacturer_reference:
        return False
    return True


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip("` \n\r")
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _call_llm_profile_fallback(
    *,
    designation: str,
    manufacturer_reference: str,
    product_type: str,
    primary_function: str,
    characteristics: str,
    composition: str,
    inferred_nature: TechnicalNature,
) -> dict[str, Any]:
    if not _client:
        return {}

    model = _llm_fallback_model()
    system_prompt = (
        "Tu aides Mosam a mieux comprendre la nature technique d'un produit avant toute "
        "decision tarifaire. Tu n'as pas le droit de proposer un code douanier, une "
        "position SH/TEC, une section, un chapitre, une RGI ou un taux. "
        "Retourne uniquement un JSON valide avec les champs: "
        '{"product_type":"","family":"","primary_function":"","system_role":"unspecified",'
        '"semantic_terms":[],"technical_signals":[],"missing_discriminants":[],'
        '"confidence":0,"reasoning":""}. '
        "Le champ product_type doit etre une famille technique generique et neutre, "
        "pas un modele commercial."
    )
    user_prompt = (
        "Produit source:\n"
        f"- designation: {designation or 'non precise'}\n"
        f"- reference fabricant: {manufacturer_reference or 'non precise'}\n"
        f"- nature technique locale: {product_type or inferred_nature.name}\n"
        f"- confiance locale: {inferred_nature.confidence}\n"
        f"- fonction: {primary_function or 'non precise'}\n"
        f"- caracteristiques: {characteristics or 'non precise'}\n"
        f"- composition: {composition or 'non precise'}\n\n"
        "Corrige seulement si la nature technique locale est trop vague ou probablement "
        "mal orientee. Si les informations restent insuffisantes, garde un type generique "
        "prudent et une confiance basse."
    )
    started = time.perf_counter()
    try:
        response = _client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **chat_completion_kwargs(model, max_tokens=500, temperature=0.1),
        )
        usage = getattr(response, "usage", None)
        record_telemetry_call(
            "functional_profile_llm",
            model=model,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            prompt_chars=len(system_prompt) + len(user_prompt),
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            success=True,
        )
        content = response.choices[0].message.content or ""
        parsed = _extract_json_object(content)
        if parsed:
            increment_telemetry("functional_profile_llm_fallback_used")
        return parsed
    except Exception:
        record_telemetry_call(
            "functional_profile_llm",
            model=model,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            prompt_chars=len(system_prompt) + len(user_prompt),
            success=False,
        )
        logger.warning("[functional_profile] low-confidence LLM fallback failed", exc_info=True)
        return {}


def _merge_llm_profile_fallback(
    *,
    current_product_type: str,
    current_family: str,
    current_primary_function: str,
    current_system_role: str,
    current_semantic_terms: list[str],
    current_missing: list[str],
    current_signals: list[str],
    current_confidence: int,
    fallback: dict[str, Any],
) -> tuple[str, str, str, str, list[str], list[str], list[str], int, bool]:
    fallback_type = str(fallback.get("product_type") or "").strip()
    fallback_confidence = max(0, min(100, _safe_int(fallback.get("confidence"), 0)))
    accepted = bool(fallback_type) and fallback_confidence >= max(45, current_confidence + 10)
    if not accepted:
        return (
            current_product_type,
            current_family,
            current_primary_function,
            current_system_role,
            current_semantic_terms,
            current_missing,
            current_signals,
            current_confidence,
            False,
        )

    family = str(fallback.get("family") or "").strip() or current_family
    primary_function = (
        str(fallback.get("primary_function") or "").strip() or current_primary_function
    )
    system_role = str(fallback.get("system_role") or "").strip() or current_system_role
    semantic_terms = sorted(
        set(current_semantic_terms)
        | {term.strip() for term in _string_list(fallback.get("semantic_terms")) if term.strip()}
    )
    missing = list(dict.fromkeys(current_missing + _string_list(fallback.get("missing_discriminants"))))
    signals = list(dict.fromkeys(current_signals + _string_list(fallback.get("technical_signals"))))
    return (
        fallback_type,
        family,
        primary_function,
        system_role,
        semantic_terms,
        missing,
        signals,
        fallback_confidence,
        True,
    )


@dataclass(frozen=True)
class FunctionalProfile:
    designation: str = ""
    manufacturer_reference: str = ""
    product_type: str = ""
    technical_nature_confidence: int = 0
    technical_nature_signals: list[str] = field(default_factory=list)
    family: str = ""
    primary_function: str = ""
    characteristics: str = ""
    composition: str = ""
    system_role: str = "unspecified"
    semantic_terms: list[str] = field(default_factory=list)
    missing_discriminants: list[str] = field(default_factory=list)
    evidence_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def functional_query(self) -> str:
        parts = [
            self.product_type,
            self.primary_function,
            self.characteristics,
            self.family,
            " ".join(self.semantic_terms),
        ]
        query = " ".join(part.strip() for part in parts if part.strip())
        return re.sub(r"\s+", " ", query).strip()[:900]

    def prompt_block(self) -> str:
        lines = ["PROFIL FONCTIONNEL (sans decision tarifaire) :"]
        if self.product_type:
            lines.append(f"Type de produit : {self.product_type}")
        if self.primary_function:
            lines.append(f"Fonction principale : {self.primary_function}")
        if self.characteristics:
            lines.append(f"Capacites/caracteristiques : {self.characteristics}")
        if self.system_role != "unspecified":
            lines.append(f"Role du produit : {self.system_role}")
        if self.semantic_terms:
            lines.append(f"Termes fonctionnels : {', '.join(self.semantic_terms)}")
        if self.missing_discriminants:
            lines.append(
                "Informations discriminantes manquantes : "
                + "; ".join(self.missing_discriminants)
            )
        lines.append(
            "La position retenue doit etre compatible avec cette fonction. "
            "Le nom commercial ou la matiere seuls ne suffisent pas."
        )
        return "\n".join(lines)


def _infer_system_role(text: str) -> str:
    normalized = _normalize(text)
    component_terms = {
        "accessoire", "component", "composant", "module", "piece", "partie",
        "carte", "adaptateur", "transceiver", "capteur", "objectif",
    }
    system_terms = {
        "systeme", "appareil", "machine", "serveur", "baie", "equipement",
        "terminal", "tablette", "robot", "camera", "controleur",
    }
    words = set(normalized.split())
    component_score = len(words & component_terms)
    system_score = len(words & system_terms)
    if component_score > system_score:
        return "component_or_module"
    if system_score > component_score:
        return "standalone_system"
    return "unspecified"


def _expand_functional_vocabulary(text: str) -> list[str]:
    words = set(_normalize(text).split())
    expanded: set[str] = set()
    for triggers, terms in _FUNCTIONAL_VOCABULARY:
        if words & triggers:
            expanded.update(terms)
    return sorted(expanded)


def build_functional_profile(
    source_text: str,
    product_identification: dict[str, Any] | None = None,
) -> FunctionalProfile:
    sections = _parse_sections(source_text)
    identification = product_identification if isinstance(product_identification, dict) else {}
    identified = not bool(identification.get("skipped"))

    designation = sections.get("designation", "")
    if not designation:
        designation = str(identification.get("product_name") or "").strip()
    if not designation and "\n" not in str(source_text or ""):
        designation = str(source_text or "").strip()

    product_type = str(identification.get("product_type") or "").strip() if identified else ""
    family = str(identification.get("family") or "").strip() if identified else ""
    primary_function = sections.get("primary_function", "")
    if identified and identification.get("function_usage"):
        primary_function = str(identification["function_usage"]).strip()
    characteristics = sections.get("characteristics", "")
    if identified:
        technical = _string_list(identification.get("technical_characteristics"))
        if technical:
            characteristics = " ".join(technical)
    composition = sections.get("composition", "")
    if identified:
        materials = _string_list(identification.get("materials"))
        if materials:
            composition = " ".join(materials)

    evidence_sources: list[str] = []
    if sections:
        evidence_sources.append("structured_input")
    if identified:
        evidence_sources.append(str(identification.get("identification_method") or "identification"))
    missing = _string_list(identification.get("missing_for_customs")) if identified else []
    inferred_nature = infer_technical_nature(
        designation,
        primary_function,
        characteristics,
        composition,
    )
    if not product_type and inferred_nature.name != "unspecified product":
        product_type = inferred_nature.name
    nature_confidence = (
        int(identification.get("identification_confidence") or 0)
        if product_type and identified
        else inferred_nature.confidence
    )
    nature_signals = list(inferred_nature.matched_signals)
    system_role = _infer_system_role(
        " ".join([designation, product_type, family, primary_function, characteristics])
    )
    semantic_terms = _expand_functional_vocabulary(
        " ".join([designation, product_type, family, primary_function, characteristics])
    )
    llm_fallback_used = False
    if _needs_llm_profile_fallback(
        sections=sections,
        identification=identification,
        inferred_nature=inferred_nature,
        product_type=product_type or inferred_nature.name,
        primary_function=primary_function,
        characteristics=characteristics,
    ):
        fallback = _call_llm_profile_fallback(
            designation=designation,
            manufacturer_reference=sections.get("manufacturer_reference", ""),
            product_type=product_type or inferred_nature.name,
            primary_function=primary_function,
            characteristics=characteristics,
            composition=composition,
            inferred_nature=inferred_nature,
        )
        (
            product_type,
            family,
            primary_function,
            system_role,
            semantic_terms,
            missing,
            nature_signals,
            nature_confidence,
            llm_fallback_used,
        ) = _merge_llm_profile_fallback(
            current_product_type=product_type or "unspecified product",
            current_family=family,
            current_primary_function=primary_function,
            current_system_role=system_role,
            current_semantic_terms=semantic_terms,
            current_missing=missing,
            current_signals=nature_signals,
            current_confidence=max(0, min(100, nature_confidence)),
            fallback=fallback,
        )
    if llm_fallback_used and "functional_profile_llm_fallback" not in evidence_sources:
        evidence_sources.append("functional_profile_llm_fallback")

    return FunctionalProfile(
        designation=designation,
        manufacturer_reference=sections.get("manufacturer_reference", ""),
        product_type=product_type or "unspecified product",
        technical_nature_confidence=max(0, min(100, nature_confidence)),
        technical_nature_signals=nature_signals,
        family=family,
        primary_function=primary_function,
        characteristics=characteristics,
        composition=composition,
        system_role=system_role,
        semantic_terms=semantic_terms,
        missing_discriminants=missing,
        evidence_sources=evidence_sources,
    )
