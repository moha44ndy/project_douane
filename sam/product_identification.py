"""Agent d'identification produit (connaissance OpenAI) avant classification TEC.

Le LLM identifie et enrichit la description marchandise ; il ne choisit jamais de code SH.

Architecture :
1. Detection du type d'entree (nom commercial / reference constructeur / description libre)
2. Prompt specialise selon le type
3. Boucle de retry conditionnelle (si confiance < 80%)
4. Double confiance : identification_confidence + classification_confidence -> finale = min()
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from .config.settings import Config
from .openai_web_search import identify_with_openai_web_search, openai_web_search_enabled

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=Config.OPENAI_API_KEY)

_DOSSIER_SECTIONS = ("composition", "usage", "capacite", "caracteristique", "specification")

_RELIABILITY_THRESHOLD = 80
_MAX_ATTEMPTS = 3


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
    if looks_like_structured_dossier(text):
        return False
    if description_is_already_rich(text):
        return False
    return True


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
    web_sources: list[dict[str, str]] = field(default_factory=list)
    web_search_queries: list[str] = field(default_factory=list)
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
            "web_sources": self.web_sources,
            "web_search_queries": self.web_search_queries,
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


def _retry_prompt_attempt3(original: str) -> str:
    return (
        f"Derniere tentative pour identifier la reference '{original}'. "
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
    response = _client.chat.completions.create(
        model=Config.MOSAM_MODEL or "gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1200,
        temperature=0.2,
    )
    content = response.choices[0].message.content
    return content or ""


def _call_with_optional_web(
    user_prompt: str,
    *,
    system_prompt: str,
) -> tuple[str, list[dict[str, str]], list[str], bool]:
    """Retourne (texte brut, sources web, requetes web, web_search_used)."""
    if openai_web_search_enabled():
        try:
            raw, sources, queries = identify_with_openai_web_search(
                instructions=system_prompt,
                user_input=user_prompt,
            )
            return raw, sources, queries, True
        except Exception as exc:
            logger.warning("[product_identification] recherche web echouee: %s", exc)
    raw = _call_identification_llm(user_prompt, system_prompt=system_prompt)
    return raw, [], [], False


# ---------------------------------------------------------------------------
# Reliability check
# ---------------------------------------------------------------------------

def _is_identification_reliable(identification: ProductIdentification) -> bool:
    """Fiable si confiance >= seuil ET product_type + function_usage renseignes."""
    if identification.identification_confidence < _RELIABILITY_THRESHOLD:
        return False
    if not identification.product_type.strip():
        return False
    if not identification.function_usage.strip():
        return False
    return True


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
        return ProductIdentification(
            original_query=original,
            enriched_description=original,
            product_name=original.split("\n", 1)[0][:120],
            identification_confidence=100,
            skipped=True,
            skip_reason="already_detailed_or_disabled",
        )

    input_type = detect_input_type(original)
    system_prompt = _get_system_prompt(input_type, use_web=openai_web_search_enabled())

    logger.info(
        "[product_identification] input_type=%s for '%s'",
        input_type, original[:50],
    )

    user_prompt = (
        f"{'Reference a identifier' if input_type == InputType.MANUFACTURER_REF else 'Description utilisateur'}"
        f" :\n{original}\n\n"
        "Construis la fiche d'identification marchandise (sans code douanier)."
    )

    # --- Attempt 1 ---
    try:
        raw, web_sources, web_queries, web_used = _call_with_optional_web(
            user_prompt, system_prompt=system_prompt,
        )
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

    if _is_identification_reliable(best):
        logger.info(
            "[product_identification] fiable attempt=1 (conf=%d, type='%s', method='%s')",
            best.identification_confidence, best.product_type[:30],
            best.identification_method[:30],
        )
        return best

    if input_type != InputType.MANUFACTURER_REF:
        logger.debug(
            "[product_identification] non fiable mais input_type=%s, pas de retry (conf=%d)",
            input_type, best.identification_confidence,
        )
        return best

    logger.info(
        "[product_identification] non fiable pour ref '%s' (conf=%d) -> retry",
        original[:40], best.identification_confidence,
    )

    all_sources = list(web_sources)
    all_queries = list(web_queries)

    # --- Attempt 2 ---
    retry_prompt = _retry_prompt_attempt2(original)
    retry_system = _system_prompt_manufacturer_ref(use_web=openai_web_search_enabled())
    try:
        raw, r_sources, r_queries, r_web = _call_with_optional_web(
            retry_prompt, system_prompt=retry_system,
        )
        all_sources.extend(r_sources)
        all_queries.extend(r_queries)
        web_used = web_used or r_web

        parsed = _parse_identification_json(raw, fallback_query=original)
        candidate = _build_identification(
            parsed, original, input_type, web_used, all_sources, all_queries, attempt_count=2,
        )
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
            return best
    except Exception as exc:
        logger.warning("[product_identification] retry 2 echoue: %s", exc)

    # --- Attempt 3 (derniere chance) ---
    retry_prompt = _retry_prompt_attempt3(original)
    try:
        raw, r_sources, r_queries, r_web = _call_with_optional_web(
            retry_prompt, system_prompt=retry_system,
        )
        all_sources.extend(r_sources)
        all_queries.extend(r_queries)
        web_used = web_used or r_web

        parsed = _parse_identification_json(raw, fallback_query=original)
        candidate = _build_identification(
            parsed, original, input_type, web_used, all_sources, all_queries, attempt_count=3,
        )
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
