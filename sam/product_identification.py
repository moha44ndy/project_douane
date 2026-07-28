"""Agent d'identification produit (connaissance OpenAI) avant classification TEC.

Le LLM identifie et enrichit la description marchandise ; il ne choisit jamais de code SH.

Architecture :
1. Detection du type d'entree (nom commercial / reference constructeur / description libre)
2. Prompt specialise selon le type
3. Boucle de retry conditionnelle (si confiance < 80%)
4. Double confiance : identification_confidence + classification_confidence -> finale = min()
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from .cache import cache_get, cache_set
from .config.settings import Config
from .openai_compat import chat_completion_kwargs
from .openai_web_search import identify_with_openai_web_search, openai_web_search_enabled
from .telemetry import increment_telemetry, record_telemetry_call

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=Config.OPENAI_API_KEY)

_DOSSIER_SECTIONS = ("composition", "usage", "capacite", "caracteristique", "specification")

_RELIABILITY_THRESHOLD = 80
_MAX_ATTEMPTS = 3
_GENERIC_PRODUCT_TYPES = {
    "product",
    "produit",
    "device",
    "appareil",
    "equipment",
    "equipement",
    "electronic device",
    "electronic equipment",
    "electronic module",
    "module electronique",
    "industrial equipment",
    "machine",
    "system",
    "systeme",
    "component",
    "composant",
}
_GENERIC_FUNCTION_TERMS = {
    "general use",
    "usage general",
    "industrial use",
    "usage industriel",
    "electrical use",
    "electronic use",
    "various applications",
    "applications diverses",
}
_REFERENCE_MISSING_HINTS = (
    "fonction exacte du produit",
    "nature technique confirmee",
    "role systeme: appareil complet ou composant",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def product_identification_enabled() -> bool:
    if not Config.OPENAI_API_KEY:
        return False
    return bool(Config.MOSAM_PRODUCT_IDENTIFICATION_ENABLED)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def looks_like_structured_dossier(text: str) -> bool:
    """True si l'utilisateur a deja fourni une fiche produit exploitable."""
    normalized = _normalize(text)
    if not normalized:
        return False
    has_product_header = bool(
        re.search(r"^(produit|marchandise|article|designation)\s*:", normalized, re.MULTILINE)
    )
    section_hits = sum(1 for keyword in _DOSSIER_SECTIONS if keyword in normalized)
    if has_product_header and section_hits >= 1:
        return True
    if section_hits >= 2:
        return True
    if re.search(r"\d+(?:[.,]\d+)?\s*%\s*\w+", text or ""):
        return bool(re.search(r"\b(?:usage|composition|capacite)\b", normalized))
    return False


def description_is_already_rich(text: str) -> bool:
    """True si la description utilisateur est deja assez detaillee pour classer sans agent."""
    normalized = _normalize(text)
    if len(normalized) > 450:
        return True
    signals = 0
    if re.search(r"\d+(?:[.,]\d+)?\s*%\s*\w+", text or ""):
        signals += 1
    if any(keyword in normalized for keyword in _DOSSIER_SECTIONS):
        signals += 1
    if re.search(r"\b(?:en\s+)?(?:cuir|textile|plastique|metal|aluminium|bois|caoutchouc)\b", normalized):
        signals += 1
    if re.search(r"\b(?:pour|destine|usage|fonction|servant)\b", normalized):
        signals += 1
    return signals >= 3


def should_run_product_identification(query: str) -> bool:
    text = (query or "").strip()
    if not text or not product_identification_enabled():
        return False
    if detect_input_type(text) == InputType.MANUFACTURER_REF:
        return True
    if looks_like_structured_dossier(text):
        return False
    if description_is_already_rich(text):
        return False
    return True


def _web_search_policy() -> str:
    policy = (Config.MOSAM_WEB_SEARCH_POLICY or "auto").strip().lower()
    if policy in {"always", "never", "manufacturer_only", "auto"}:
        return policy
    return "auto"


def should_use_web_search_for_identification(query: str, input_type: str) -> bool:
    """Gate la recherche web pour limiter les couts et la latence."""
    if not openai_web_search_enabled():
        return False

    policy = _web_search_policy()
    if policy == "never":
        return False
    if policy == "always":
        return True
    if policy == "manufacturer_only":
        return input_type == InputType.MANUFACTURER_REF

    # policy == "auto"
    if input_type == InputType.MANUFACTURER_REF:
        return True

    text = (query or "").strip()
    if not text:
        return False
    if looks_like_structured_dossier(text) or description_is_already_rich(text):
        return False

    words = [w for w in re.split(r"\s+", text) if w]
    max_words = max(1, Config.MOSAM_WEB_SEARCH_MAX_SHORT_QUERY_WORDS)
    max_chars = max(8, Config.MOSAM_WEB_SEARCH_MAX_SHORT_QUERY_CHARS)
    return len(words) <= max_words and len(text) <= max_chars


def _extract_reference_for_cache(query: str) -> str:
    text = re.sub(r"\s+", " ", (query or "").strip())
    labelled = re.search(
        r"(?i)\b(?:reference\s+fabricant|manufacturer\s+reference|part\s+number|mpn)\s*:?\s*([^,;\n]+)",
        text,
    )
    if labelled:
        labelled_text = labelled.group(1).strip()
        labelled_candidates = re.findall(
            r"\b[A-Z0-9]+(?:[-_./][A-Z0-9]+)+\b",
            labelled_text,
            flags=re.IGNORECASE,
        )
        if labelled_candidates:
            return labelled_candidates[0].strip()
        labelled_compact = re.findall(
            r"\b[A-Z]{1,8}\d[A-Z0-9]{2,}\b",
            labelled_text,
            flags=re.IGNORECASE,
        )
        if labelled_compact:
            return labelled_compact[0].strip()
    candidates = re.findall(r"\b[A-Z0-9]+(?:[-_./][A-Z0-9]+)+\b", text, flags=re.IGNORECASE)
    if candidates:
        return candidates[0].strip()
    compact = re.findall(r"\b[A-Z]{1,8}\d[A-Z0-9]{2,}\b", text, flags=re.IGNORECASE)
    return compact[0].strip() if compact else ""


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in values:
        cleaned = re.sub(r"\s+", " ", str(item or "").strip())
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


def _looks_generic_product_type(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", _normalize(value)).strip()
    return not normalized or normalized in _GENERIC_PRODUCT_TYPES


def _looks_generic_function(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", _normalize(value)).strip()
    return not normalized or normalized in _GENERIC_FUNCTION_TERMS or len(normalized.split()) <= 2


def _normalize_identification_output(
    original: str,
    identification: ProductIdentification,
) -> ProductIdentification:
    identification.materials = _unique_preserve_order(identification.materials)[:8]
    identification.technical_characteristics = _unique_preserve_order(
        identification.technical_characteristics
    )[:10]
    identification.missing_for_customs = _unique_preserve_order(
        identification.missing_for_customs
    )[:10]

    if identification.input_type == InputType.MANUFACTURER_REF and not identification.manufacturer_part_number:
        identification.manufacturer_part_number = _extract_reference_for_cache(original)

    if (
        identification.input_type == InputType.MANUFACTURER_REF
        and identification.manufacturer_part_number
        and identification.manufacturer_part_number not in identification.enriched_description
    ):
        identification.enriched_description = (
            f"Reference fabricant : {identification.manufacturer_part_number}\n"
            f"{identification.enriched_description.strip() or original}"
        ).strip()

    generic_type = _looks_generic_product_type(identification.product_type)
    generic_function = _looks_generic_function(identification.function_usage)

    if identification.input_type == InputType.MANUFACTURER_REF:
        identification.missing_for_customs = _unique_preserve_order(
            identification.missing_for_customs + list(_REFERENCE_MISSING_HINTS)
        )[:10]

    if generic_type:
        identification.identification_confidence = min(identification.identification_confidence, 55)
        identification.missing_for_customs = _unique_preserve_order(
            identification.missing_for_customs + ["type de produit exact a confirmer"]
        )[:10]

    if generic_function:
        identification.identification_confidence = min(identification.identification_confidence, 60)
        identification.missing_for_customs = _unique_preserve_order(
            identification.missing_for_customs + ["fonction principale exacte a confirmer"]
        )[:10]

    if (
        identification.input_type == InputType.MANUFACTURER_REF
        and not identification.technical_characteristics
    ):
        identification.missing_for_customs = _unique_preserve_order(
            identification.missing_for_customs + ["caracteristiques techniques discriminantes"]
        )[:10]

    if not identification.why_not_other_products.strip() and identification.identification_confidence < 80:
        identification.notes = (
            (identification.notes or "")
            + " Produits proches non suffisamment elimines."
        ).strip()

    return identification


def _identification_cache_key(query: str) -> str:
    cache_basis = query or ""
    ref = _extract_reference_for_cache(cache_basis)
    if ref and (
        detect_input_type(cache_basis) == InputType.MANUFACTURER_REF
        or re.search(r"[-_./]", ref)
        or re.search(r"(?i)\b(?:reference\s+fabricant|manufacturer\s+reference|part\s+number|mpn)\b", cache_basis)
    ):
        cache_basis = f"manufacturer_ref:{ref}"
    normalized = re.sub(r"\s+", " ", cache_basis.strip().lower())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"product_identification:v1:{digest}"


# ---------------------------------------------------------------------------
# Input type detection
# ---------------------------------------------------------------------------

class InputType:
    COMMERCIAL_NAME = "commercial_name"
    MANUFACTURER_REF = "manufacturer_ref"
    FREE_DESCRIPTION = "free_description"


def detect_input_type(text: str) -> str:
    """Detecte le type d'entree utilisateur.

    - commercial_name  : iPhone 15, MacBook Pro, Redmi 14C, Galaxy A15
    - manufacturer_ref : 6ES7515-2AM01-0AB0, FP2-FX20, SFP-10G-SR
    - free_description : sac de voyage en cuir, telephone portable
    """
    t = (text or "").strip()
    if not t:
        return InputType.FREE_DESCRIPTION

    has_alpha = bool(re.search(r"[A-Za-z]", t))
    has_digit = bool(re.search(r"\d", t))

    if not has_alpha and not has_digit:
        return InputType.FREE_DESCRIPTION

    if re.search(r"(?i)\b(?:reference\s+fabricant|manufacturer\s+reference|part\s+number|mpn)\b", t):
        if has_alpha and has_digit:
            return InputType.MANUFACTURER_REF

    labelled_ref = re.search(
        r"(?im)^\s*(?:reference\s+fabricant|manufacturer\s+reference|part\s+number|mpn)\s*:\s*(.+?)\s*$",
        t,
    )
    if labelled_ref:
        ref_value = labelled_ref.group(1).strip()
        if ref_value and bool(re.search(r"[A-Za-z]", ref_value)) and bool(re.search(r"\d", ref_value)):
            return InputType.MANUFACTURER_REF

    if " " not in t and has_alpha and has_digit:
        return InputType.MANUFACTURER_REF

    special_count = sum(1 for c in t if c in "-_./")
    words = t.split()

    if special_count >= 2 and len(words) <= 3 and has_digit:
        return InputType.MANUFACTURER_REF

    if len(words) <= 2 and has_digit and not has_alpha:
        return InputType.FREE_DESCRIPTION

    if has_alpha and has_digit and len(words) <= 4:
        alpha_ratio = sum(1 for c in t if c.isalpha()) / max(len(t), 1)
        digit_ratio = sum(1 for c in t if c.isdigit()) / max(len(t), 1)

        if digit_ratio > 0.4 and special_count >= 1:
            return InputType.MANUFACTURER_REF

        if alpha_ratio > 0.5 and len(words) >= 2:
            return InputType.COMMERCIAL_NAME

        if len(words) == 1 and special_count >= 1:
            return InputType.MANUFACTURER_REF

    if len(words) >= 4:
        return InputType.FREE_DESCRIPTION

    if has_alpha and len(words) <= 3:
        return InputType.COMMERCIAL_NAME

    return InputType.FREE_DESCRIPTION


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProductIdentification:
    original_query: str
    input_type: str = InputType.FREE_DESCRIPTION
    product_name: str = ""
    product_type: str = ""
    family: str = ""
    manufacturer: str = ""
    manufacturer_part_number: str = ""
    commercial_name: str = ""
    function_usage: str = ""
    why_not_other_products: str = ""
    materials: list[str] = field(default_factory=list)
    technical_characteristics: list[str] = field(default_factory=list)
    missing_for_customs: list[str] = field(default_factory=list)
    identification_confidence: int = 0
    identification_method: str = ""
    reasoning: str = ""
    enriched_description: str = ""
    notes: str = ""
    web_search_used: bool = False
    web_search_failed: bool = False
    web_sources: list[dict[str, str]] = field(default_factory=list)
    web_search_queries: list[str] = field(default_factory=list)
    identification_unstable: bool = False
    skipped: bool = False
    skip_reason: str = ""
    attempt_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "input_type": self.input_type,
            "product_name": self.product_name,
            "product_type": self.product_type,
            "family": self.family,
            "manufacturer": self.manufacturer,
            "manufacturer_part_number": self.manufacturer_part_number,
            "commercial_name": self.commercial_name,
            "function_usage": self.function_usage,
            "why_not_other_products": self.why_not_other_products,
            "materials": self.materials,
            "technical_characteristics": self.technical_characteristics,
            "missing_for_customs": self.missing_for_customs,
            "identification_confidence": self.identification_confidence,
            "identification_method": self.identification_method,
            "reasoning": self.reasoning,
            "enriched_description": self.enriched_description,
            "notes": self.notes,
            "web_search_used": self.web_search_used,
            "web_search_failed": self.web_search_failed,
            "web_sources": self.web_sources,
            "web_search_queries": self.web_search_queries,
            "identification_unstable": self.identification_unstable,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "attempt_count": self.attempt_count,
        }


# ---------------------------------------------------------------------------
# JSON output schema (shared across all prompts)
# ---------------------------------------------------------------------------

_JSON_SCHEMA = (
    '{"product_name":"","product_type":"","family":"","manufacturer":"",'
    '"manufacturer_part_number":"","commercial_name":"","function_usage":"",'
    '"why_not_other_products":"","materials":[],"technical_characteristics":[],'
    '"missing_for_customs":[],"identification_confidence":0,'
    '"identification_method":"","reasoning":"","enriched_description":"","notes":""}'
)

_JSON_FIELDS_DOC = (
    "manufacturer = fabricant/marque (ex: Samsung, Caterpillar, Schneider). "
    "manufacturer_part_number = reference fabricant si connue (ex: SM-A156B, CAT 320). "
    "commercial_name = nom commercial du produit (ex: Galaxy A15, iPhone 16 Pro Max). "
    "family = famille de produits (ex: 'automates programmables', 'smartphones', "
    "'connecteurs industriels', 'modules optiques'). "
    "why_not_other_products = raisonnement par elimination : explique pourquoi ce produit "
    "N'EST PAS d'autres produits similaires qui pourraient etre confondus. "
    "Exemples : 'Ce n'est pas un switch car la documentation constructeur decrit un automate "
    "programmable. Ce n'est pas un variateur car absence de puissance nominale. "
    "Ce n'est pas un module I/O car presence d'un processeur integre.' "
    "Ce champ est OBLIGATOIRE : tu dois toujours identifier au moins 2-3 produits similaires "
    "que ce produit N'EST PAS, et expliquer pourquoi. "
    "identification_method = methode utilisee (ex: 'catalogue fabricant', 'fiche technique', "
    "'connaissance generale', 'recherche web'). "
    "reasoning = explication de pourquoi tu penses que c'est ce produit (1-2 phrases). "
    "identification_confidence entre 0 et 100. "
    "Le champ enriched_description doit reprendre le format fiche Mosam : "
    "Produit : ...\\nComposition :\\n- ...\\nUsage :\\n...\\nCaracteristiques :\\n- ... "
    "(sections utiles seulement)."
)

_INTERDICTIONS = (
    "INTERDICTIONS ABSOLUES : "
    "- ne jamais proposer, suggerer ou mentionner de code SH, position tarifaire, chapitre HS ou taux de droits ; "
    "- ne jamais appliquer les RGI ni choisir une nomenclature ; "
    "- ne pas inventer de specifications ultra-precises non etayees (poids exact, % matiere) : "
    "indique 'non precise' ou une fourchette prudente, et liste ce qui manque."
)


# ---------------------------------------------------------------------------
# Specialized prompts per input type
# ---------------------------------------------------------------------------

def _system_prompt_commercial_name(*, use_web: bool = False) -> str:
    web_clause = (
        "Tu peux consulter internet via l'outil de recherche pour identifier le produit "
        "(fiche fabricant, usage courant, materiaux). "
        if use_web
        else "Tu t'appuies sur ta connaissance generale du produit. "
    )
    return (
        "Tu es l'agent d'identification marchandise de Mosam (douane CEDEAO). "
        "L'utilisateur a saisi un NOM COMMERCIAL de produit. "
        "Ta mission : identifier precisement ce produit, son fabricant, sa categorie "
        "et sa fonction principale. "
        f"{web_clause}"
        f"{_INTERDICTIONS} "
        f"Reponds UNIQUEMENT en JSON valide, sans markdown, de la forme : {_JSON_SCHEMA}. "
        f"{_JSON_FIELDS_DOC}"
    )


def _system_prompt_manufacturer_ref(*, use_web: bool = False) -> str:
    web_clause = (
        "Tu DOIS consulter internet via l'outil de recherche pour identifier cette reference "
        "(catalogue fabricant, datasheet, fiche technique). "
        if use_web
        else "Tu t'appuies sur ta connaissance generale. "
    )
    return (
        "Tu es l'agent d'identification marchandise de Mosam (douane CEDEAO). "
        "Tu recois une REFERENCE CONSTRUCTEUR INDUSTRIELLE (code produit technique). "
        "Ta mission : identifier precisement le fabricant, le nom commercial, "
        "la categorie du produit, sa fonction principale et son usage. "
        "Si tu n'es pas suffisamment certain, indique-le explicitement au lieu de deviner. "
        f"{web_clause}"
        f"{_INTERDICTIONS} "
        f"Reponds UNIQUEMENT en JSON valide, sans markdown, de la forme : {_JSON_SCHEMA}. "
        f"{_JSON_FIELDS_DOC}"
    )


def _system_prompt_free_description(*, use_web: bool = False) -> str:
    web_clause = (
        "Tu peux consulter internet via l'outil de recherche pour identifier le produit "
        "(fiche fabricant, usage courant, materiaux). "
        if use_web
        else "Tu t'appuies sur ta connaissance generale du produit. "
    )
    return (
        "Tu es l'agent d'identification marchandise de Mosam (douane CEDEAO). "
        "Ta mission : comprendre ce qu'est le produit decrit par l'utilisateur. "
        "Tu produis une fiche technique structuree pour un classificateur douanier. "
        f"{web_clause}"
        f"{_INTERDICTIONS} "
        f"Reponds UNIQUEMENT en JSON valide, sans markdown, de la forme : {_JSON_SCHEMA}. "
        f"{_JSON_FIELDS_DOC}"
    )


def _get_system_prompt(input_type: str, *, use_web: bool = False) -> str:
    if input_type == InputType.COMMERCIAL_NAME:
        return _system_prompt_commercial_name(use_web=use_web)
    if input_type == InputType.MANUFACTURER_REF:
        return _system_prompt_manufacturer_ref(use_web=use_web)
    return _system_prompt_free_description(use_web=use_web)


# ---------------------------------------------------------------------------
# Retry prompts (manufacturer_ref only — others pass on first attempt)
# ---------------------------------------------------------------------------

def _retry_prompt_attempt2(original: str) -> str:
    return (
        f"Cette reference '{original}' semble etre une reference constructeur. "
        "Recherche les catalogues, fiches techniques et documentations fabricant "
        "afin d'identifier precisement le produit. "
        "Identifie le fabricant, le nom commercial, la categorie et la fonction principale.\n\n"
        f"Reference a identifier :\n{original}\n\n"
        "Construis la fiche d'identification marchandise (sans code douanier). "
        "Tu DOIS remplir product_type et function_usage."
    )


def _retry_prompt_attempt3(original: str, *, web_failed: bool = False) -> str:
    web_note = (
        "IMPORTANT : la recherche internet a echoue. N'invente PAS un produit different "
        "de la reference. Si tu ne connais pas cette reference, mets identification_confidence "
        "<= 30 et indique l'incertitude.\n\n"
        if web_failed
        else ""
    )
    return (
        f"Derniere tentative pour identifier la reference '{original}'. "
        f"{web_note}"
        "Si plusieurs produits existent pour cette reference, choisis le plus probable "
        "et explique pourquoi dans le champ 'reasoning'. "
        "Si aucune identification fiable n'est possible, mets identification_confidence "
        "a une valeur basse (<30) et indique clairement dans 'reasoning' que "
        "l'identification est incertaine.\n\n"
        f"Reference a identifier :\n{original}\n\n"
        "Construis la fiche d'identification marchandise (sans code douanier). "
        "Tu DOIS remplir product_type et function_usage meme avec une hypothese."
    )


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

def _parse_identification_json(raw: str, *, fallback_query: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip("` \n\r")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {
        "product_name": fallback_query[:120],
        "product_type": "",
        "function_usage": "",
        "materials": [],
        "technical_characteristics": [],
        "missing_for_customs": ["Identification automatique non parsee — preciser la nature du produit"],
        "identification_confidence": 35,
        "identification_method": "echec_parsing",
        "reasoning": "Reponse LLM non JSON ; fiche minimale generee.",
        "enriched_description": f"Produit : {fallback_query.strip()}",
        "notes": "Reponse LLM non JSON ; fiche minimale generee.",
    }


def _call_identification_llm(
    user_prompt: str,
    *,
    system_prompt: str,
) -> str:
    model = Config.MOSAM_IDENTIFICATION_MODEL or "gpt-5"
    started = time.perf_counter()
    try:
        response = _client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **chat_completion_kwargs(model, max_tokens=1200, temperature=0.2),
        )
        usage = getattr(response, "usage", None)
        record_telemetry_call(
            "identification_llm",
            model=model,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            prompt_chars=len(user_prompt or "") + len(system_prompt or ""),
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            success=True,
        )
        content = response.choices[0].message.content
        return content or ""
    except Exception:
        record_telemetry_call(
            "identification_llm",
            model=model,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            prompt_chars=len(user_prompt or "") + len(system_prompt or ""),
            success=False,
        )
        raise


def _call_with_optional_web(
    user_prompt: str,
    *,
    system_prompt: str,
    use_web: bool,
) -> tuple[str, list[dict[str, str]], list[str], bool, bool]:
    """Retourne (texte brut, sources web, requetes web, web_search_used, web_search_failed)."""
    if use_web:
        increment_telemetry("web_search_attempted")
        try:
            raw, sources, queries = identify_with_openai_web_search(
                instructions=system_prompt,
                user_input=user_prompt,
            )
            return raw, sources, queries, True, False
        except Exception as exc:
            logger.warning("[product_identification] recherche web echouee: %s", exc)
            raw = _call_identification_llm(user_prompt, system_prompt=system_prompt)
            return raw, [], [], False, True
    raw = _call_identification_llm(user_prompt, system_prompt=system_prompt)
    return raw, [], [], False, False


# ---------------------------------------------------------------------------
# Reliability check
# ---------------------------------------------------------------------------

def _is_identification_reliable(identification: ProductIdentification) -> bool:
    """Fiable si confiance >= seuil ET product_type + function_usage renseignes."""
    if identification.identification_unstable:
        return False
    if identification.identification_confidence < _RELIABILITY_THRESHOLD:
        return False
    if not identification.product_type.strip():
        return False
    if not identification.function_usage.strip():
        return False
    if identification.input_type == InputType.MANUFACTURER_REF and not _identification_matches_reference(
        identification.original_query,
        identification,
    ):
        return False
    return True


def _reference_tokens(original: str) -> list[str]:
    """Tokens significatifs extraits d'une reference constructeur."""
    tokens = re.findall(r"[A-Za-z0-9]{2,}", original or "")
    return [t.lower() for t in tokens if len(t) >= 2]


def _identification_matches_reference(
    original: str,
    identification: ProductIdentification,
) -> bool:
    """Verifie que l'identification reste liee a la reference saisie."""
    original_clean = (original or "").strip()
    if not original_clean:
        return True

    haystack = " ".join(
        filter(
            None,
            [
                identification.product_name,
                identification.manufacturer_part_number,
                identification.commercial_name,
                identification.manufacturer,
                identification.product_type,
                identification.reasoning,
            ],
        )
    )
    haystack_lower = haystack.lower()
    original_lower = original_clean.lower()

    compact_original = re.sub(r"[^a-z0-9]", "", original_lower)
    compact_haystack = re.sub(r"[^a-z0-9]", "", haystack_lower)
    if len(compact_original) >= 4 and compact_original in compact_haystack:
        return True

    mpn = (identification.manufacturer_part_number or "").strip().lower()
    if mpn and (mpn == original_lower or original_lower in mpn or mpn in original_lower):
        return True

    tokens = _reference_tokens(original_clean)
    if not tokens:
        return True

    alpha_num_tokens = [
        t for t in tokens
        if any(c.isdigit() for c in t) and any(c.isalpha() for c in t)
    ]
    long_tokens = [t for t in tokens if len(t) >= 5]
    if alpha_num_tokens and all(t in haystack_lower for t in alpha_num_tokens):
        return True
    if long_tokens and all(t in haystack_lower for t in long_tokens):
        return True

    matched = sum(1 for t in tokens if t in haystack_lower)
    return matched >= max(2, len(tokens))


def _finalize_identification_stability(
    original: str,
    identification: ProductIdentification,
) -> ProductIdentification:
    """Marque et assainit une identification incertaine ou incoherente."""
    unreliable = not _is_identification_reliable(identification)
    ref_mismatch = (
        identification.input_type == InputType.MANUFACTURER_REF
        and not _identification_matches_reference(original, identification)
    )

    if not unreliable and not ref_mismatch:
        return identification

    identification.identification_unstable = True
    identification.identification_confidence = min(
        identification.identification_confidence,
        45 if ref_mismatch else 55,
    )

    if ref_mismatch:
        identification.enriched_description = (
            f"Reference utilisateur : {original.strip()}\n"
            "Identification incertaine — la reference n'a pas ete confirmee.\n"
            "Preciser le fabricant, la nature et la fonction du produit avant validation."
        )
        identification.notes = (
            (identification.notes or "")
            + " Identification instable : reference non confirmee (hypothese ecartee)."
        ).strip()
    elif unreliable:
        parts = [f"Reference utilisateur : {original.strip()}", "Identification incertaine — a valider."]
        if identification.product_type.strip():
            parts.append(f"Hypothese (non confirmee) : {identification.product_type.strip()}")
        if identification.function_usage.strip():
            parts.append(f"Fonction probable : {identification.function_usage.strip()}")
        identification.enriched_description = "\n".join(parts)
        if "identification incertaine" not in (identification.notes or "").lower():
            identification.notes = (
                (identification.notes or "") + " Identification instable apres tentatives."
            ).strip()

    return identification


# ---------------------------------------------------------------------------
# Build result from parsed JSON
# ---------------------------------------------------------------------------

def _build_identification(
    parsed: dict[str, Any],
    original: str,
    input_type: str,
    web_search_used: bool,
    web_sources: list[dict[str, str]],
    web_search_queries: list[str],
    attempt_count: int = 1,
) -> ProductIdentification:
    enriched = str(parsed.get("enriched_description") or "").strip() or original
    notes = str(parsed.get("notes") or "").strip()
    if web_search_used and (web_sources or web_search_queries):
        notes = (notes + " Recherche internet OpenAI consultee.").strip()
    return ProductIdentification(
        original_query=original,
        input_type=input_type,
        product_name=str(parsed.get("product_name") or original[:120]).strip(),
        product_type=str(parsed.get("product_type") or "").strip(),
        family=str(parsed.get("family") or "").strip(),
        manufacturer=str(parsed.get("manufacturer") or "").strip(),
        manufacturer_part_number=str(parsed.get("manufacturer_part_number") or "").strip(),
        commercial_name=str(parsed.get("commercial_name") or "").strip(),
        function_usage=str(parsed.get("function_usage") or "").strip(),
        why_not_other_products=str(parsed.get("why_not_other_products") or "").strip(),
        materials=[str(item).strip() for item in (parsed.get("materials") or []) if str(item).strip()],
        technical_characteristics=[
            str(item).strip()
            for item in (parsed.get("technical_characteristics") or [])
            if str(item).strip()
        ],
        missing_for_customs=[
            str(item).strip()
            for item in (parsed.get("missing_for_customs") or [])
            if str(item).strip()
        ],
        identification_confidence=max(
            0,
            min(100, int(parsed.get("identification_confidence") or 0)),
        ),
        identification_method=str(parsed.get("identification_method") or "").strip(),
        reasoning=str(parsed.get("reasoning") or "").strip(),
        enriched_description=enriched,
        notes=notes,
        web_search_used=web_search_used,
        web_sources=web_sources,
        web_search_queries=web_search_queries,
        attempt_count=attempt_count,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def identify_product(query: str) -> ProductIdentification:
    """
    Identifie et enrichit un produit.

    Flux :
    1. Detecte le type d'entree (nom commercial / reference constructeur / description)
    2. Utilise un prompt specialise selon le type
    3. Si reference constructeur et confiance < 80% : retry (max 3 tentatives)
    4. Retourne le meilleur resultat avec identification_confidence non plafonnee
    """
    original = (query or "").strip()
    if not original:
        return ProductIdentification(
            original_query="",
            skipped=True,
            skip_reason="empty_query",
        )

    if not should_run_product_identification(original):
        increment_telemetry("product_identification_skipped")
        return ProductIdentification(
            original_query=original,
            enriched_description=original,
            product_name=original.split("\n", 1)[0][:120],
            identification_confidence=100,
            skipped=True,
            skip_reason="already_detailed_or_disabled",
        )

    input_type = detect_input_type(original)
    use_web = should_use_web_search_for_identification(original, input_type)
    increment_telemetry("product_identification_requested")
    if input_type == InputType.MANUFACTURER_REF:
        increment_telemetry("manufacturer_reference_inputs")
    if use_web:
        increment_telemetry("product_identification_web_enabled")
    cache_key = _identification_cache_key(original)
    cached_raw = cache_get(cache_key)
    if isinstance(cached_raw, str) and cached_raw.strip():
        try:
            cached_data = json.loads(cached_raw)
            if isinstance(cached_data, dict):
                result = ProductIdentification(**cached_data)
                logger.info(
                    "[product_identification] cache HIT input_type=%s web=%s query='%s'",
                    input_type,
                    result.web_search_used,
                    original[:50],
                )
                increment_telemetry("product_identification_cache_hit")
                return result
        except Exception:
            logger.warning("[product_identification] cache parse failed", exc_info=True)
    increment_telemetry("product_identification_cache_miss")

    system_prompt = _get_system_prompt(input_type, use_web=use_web)

    logger.info(
        "[product_identification] input_type=%s web=%s for '%s'",
        input_type,
        use_web,
        original[:50],
    )

    user_prompt = (
        f"{'Reference a identifier' if input_type == InputType.MANUFACTURER_REF else 'Description utilisateur'}"
        f" :\n{original}\n\n"
        "Construis la fiche d'identification marchandise (sans code douanier)."
    )

    # --- Attempt 1 ---
    web_failed_any = False
    try:
        raw, web_sources, web_queries, web_used, web_failed = _call_with_optional_web(
            user_prompt, system_prompt=system_prompt, use_web=use_web,
        )
        web_failed_any = web_failed_any or web_failed
    except Exception as exc:
        logger.warning("[product_identification] echec LLM: %s", exc)
        return ProductIdentification(
            original_query=original,
            input_type=input_type,
            enriched_description=original,
            product_name=original[:120],
            identification_confidence=25,
            skipped=True,
            skip_reason="llm_error",
            notes=str(exc),
        )

    parsed = _parse_identification_json(raw, fallback_query=original)
    best = _build_identification(
        parsed, original, input_type, web_used, web_sources, web_queries, attempt_count=1,
    )
    best = _normalize_identification_output(original, best)

    if _is_identification_reliable(best):
        logger.info(
            "[product_identification] fiable attempt=1 (conf=%d, type='%s', method='%s')",
            best.identification_confidence, best.product_type[:30],
            best.identification_method[:30],
        )
        best.web_search_failed = web_failed_any and not web_used
        best = _finalize_identification_stability(original, best)
        cache_set(cache_key, best.to_dict(), ex=86400)
        return best

    if input_type != InputType.MANUFACTURER_REF:
        logger.debug(
            "[product_identification] non fiable mais input_type=%s, pas de retry (conf=%d)",
            input_type, best.identification_confidence,
        )
        best.web_search_failed = web_failed_any and not web_used
        best = _finalize_identification_stability(original, best)
        cache_set(cache_key, best.to_dict(), ex=21600)
        return best

    logger.info(
        "[product_identification] non fiable pour ref '%s' (conf=%d) -> retry",
        original[:40], best.identification_confidence,
    )

    all_sources = list(web_sources)
    all_queries = list(web_queries)

    # --- Attempt 2 ---
    retry_prompt = _retry_prompt_attempt2(original)
    retry_system = _system_prompt_manufacturer_ref(use_web=use_web)
    try:
        raw, r_sources, r_queries, r_web, r_failed = _call_with_optional_web(
            retry_prompt, system_prompt=retry_system, use_web=use_web,
        )
        web_failed_any = web_failed_any or r_failed
        all_sources.extend(r_sources)
        all_queries.extend(r_queries)
        web_used = web_used or r_web

        parsed = _parse_identification_json(raw, fallback_query=original)
        candidate = _build_identification(
            parsed, original, input_type, web_used, all_sources, all_queries, attempt_count=2,
        )
        candidate = _normalize_identification_output(original, candidate)
        if candidate.identification_confidence > best.identification_confidence:
            best = candidate
            best.attempt_count = 2

        if _is_identification_reliable(best):
            logger.info(
                "[product_identification] fiable attempt=2 (conf=%d, type='%s')",
                best.identification_confidence, best.product_type[:30],
            )
            best.web_sources = all_sources[:10]
            best.web_search_queries = list(dict.fromkeys(all_queries))[:8]
            best.web_search_used = web_used
            best.web_search_failed = web_failed_any and not web_used
            return _finalize_identification_stability(original, best)
    except Exception as exc:
        logger.warning("[product_identification] retry 2 echoue: %s", exc)

    # --- Attempt 3 (derniere chance) ---
    retry_prompt = _retry_prompt_attempt3(original, web_failed=web_failed_any)
    try:
        raw, r_sources, r_queries, r_web, r_failed = _call_with_optional_web(
            retry_prompt, system_prompt=retry_system, use_web=use_web,
        )
        web_failed_any = web_failed_any or r_failed
        all_sources.extend(r_sources)
        all_queries.extend(r_queries)
        web_used = web_used or r_web

        parsed = _parse_identification_json(raw, fallback_query=original)
        candidate = _build_identification(
            parsed, original, input_type, web_used, all_sources, all_queries, attempt_count=3,
        )
        candidate = _normalize_identification_output(original, candidate)
        if candidate.identification_confidence > best.identification_confidence:
            best = candidate
            best.attempt_count = 3

        if _is_identification_reliable(best):
            logger.info(
                "[product_identification] fiable attempt=3 (conf=%d, type='%s')",
                best.identification_confidence, best.product_type[:30],
            )
    except Exception as exc:
        logger.warning("[product_identification] retry 3 echoue: %s", exc)

    if not _is_identification_reliable(best):
        logger.warning(
            "[product_identification] non fiable apres %d tentatives pour '%s' (conf=%d)",
            _MAX_ATTEMPTS, original[:40], best.identification_confidence,
        )
        if "identification incertaine" not in (best.notes or "").lower():
            best.notes = (
                (best.notes or "")
                + " Identification incertaine apres plusieurs tentatives."
            ).strip()

    best.web_sources = all_sources[:10]
    best.web_search_queries = list(dict.fromkeys(all_queries))[:8]
    best.web_search_used = web_used
    best.web_search_failed = web_failed_any and not web_used
    best = _finalize_identification_stability(original, best)
    cache_set(cache_key, best.to_dict(), ex=21600 if best.identification_unstable else 86400)
    return best


def prepare_query_for_classification(query: str) -> tuple[str, ProductIdentification]:
    """
    Retourne (texte_a_classer, identification).
    Lance l'agent seulement si utile ; sinon repasse la requete telle quelle.
    """
    original = (query or "").strip()
    if not should_run_product_identification(original):
        logger.debug("[prepare_query] identification SKIPPED for: %s", original[:80])
        return original, ProductIdentification(
            original_query=original,
            enriched_description=original,
            skipped=True,
            skip_reason="not_needed",
        )

    identification = identify_product(original)

    if identification.identification_unstable:
        parts = [f"Reference utilisateur : {original}"]
        if _identification_matches_reference(original, identification):
            if identification.product_type.strip():
                parts.append(f"Type probable : {identification.product_type.strip()}")
            if identification.function_usage.strip():
                parts.append(f"Fonction probable : {identification.function_usage.strip()}")
        parts.append("Identification incertaine — a valider avant toute utilisation officielle.")
        text = "\n".join(parts)
    else:
        text = identification.enriched_description.strip() or original
    logger.debug(
        "[prepare_query] identification DONE for '%s' -> type='%s', function='%s', "
        "method='%s', conf=%d, attempts=%d",
        original[:40],
        identification.product_type[:40],
        identification.function_usage[:40],
        identification.identification_method[:30],
        identification.identification_confidence,
        identification.attempt_count,
    )
    return text, identification
