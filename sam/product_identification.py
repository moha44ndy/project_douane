"""Agent d'identification produit (connaissance OpenAI) avant classification TEC.

Le LLM identifie et enrichit la description marchandise ; il ne choisit jamais de code SH.
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


@dataclass
class ProductIdentification:
    original_query: str
    product_name: str = ""
    product_type: str = ""
    function_usage: str = ""
    materials: list[str] = field(default_factory=list)
    technical_characteristics: list[str] = field(default_factory=list)
    missing_for_customs: list[str] = field(default_factory=list)
    identification_confidence: int = 0
    enriched_description: str = ""
    notes: str = ""
    web_search_used: bool = False
    web_sources: list[dict[str, str]] = field(default_factory=list)
    web_search_queries: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "product_name": self.product_name,
            "product_type": self.product_type,
            "function_usage": self.function_usage,
            "materials": self.materials,
            "technical_characteristics": self.technical_characteristics,
            "missing_for_customs": self.missing_for_customs,
            "identification_confidence": self.identification_confidence,
            "enriched_description": self.enriched_description,
            "notes": self.notes,
            "web_search_used": self.web_search_used,
            "web_sources": self.web_sources,
            "web_search_queries": self.web_search_queries,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


def _identification_system_prompt(*, use_web: bool = False) -> str:
    web_clause = (
        "Tu peux consulter internet via l'outil de recherche pour identifier le produit "
        "(fiche fabricant, usage courant, materiaux). "
        "N'utilise pas internet pour deviner un code douanier. "
        if use_web
        else "Tu t'appuies sur ta connaissance generale du produit. "
    )
    return (
        "Tu es l'agent d'identification marchandise de Mosam (douane CEDEAO). "
        "Ta mission : comprendre ce qu'est le produit decrit par l'utilisateur, comme le ferait ChatGPT. "
        f"{web_clause}"
        "Tu produis une fiche technique structuree pour un classificateur douanier humain ou un second moteur. "
        "INTERDICTIONS ABSOLUES : "
        "- ne jamais proposer, suggerer ou mentionner de code SH, position tarifaire, chapitre HS ou taux de droits ; "
        "- ne jamais appliquer les RGI ni choisir une nomenclature ; "
        "- ne pas inventer de specifications ultra-precises non etayees (poids exact, % matiere) : indique « non precise » "
        "ou une fourchette prudente, et liste ce qui manque. "
        "Reponds UNIQUEMENT en JSON valide, sans markdown, de la forme : "
        '{"product_name":"","product_type":"","function_usage":"","materials":[],"technical_characteristics":[],'
        '"missing_for_customs":[],"identification_confidence":0,"enriched_description":"","notes":""}. '
        "Le champ enriched_description doit reprendre le format fiche Mosam : "
        "Produit : ...\\nComposition :\\n- ...\\nUsage :\\n...\\nCaracteristiques :\\n- ... "
        "(sections utiles seulement). "
        "identification_confidence entre 0 et 100."
    )


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
        "enriched_description": f"Produit : {fallback_query.strip()}",
        "notes": "Reponse LLM non JSON ; fiche minimale generee.",
    }


def _call_identification_llm(user_prompt: str, *, use_web: bool = False) -> str:
    response = _client.chat.completions.create(
        model=Config.MOSAM_MODEL or "gpt-4.1-mini",
        messages=[
            {"role": "system", "content": _identification_system_prompt(use_web=use_web)},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1200,
        temperature=0.2,
    )
    content = response.choices[0].message.content
    return content or ""


def _call_identification_with_optional_web(user_prompt: str) -> tuple[str, list[dict[str, str]], list[str], bool]:
    """Retourne (texte brut, sources web, requetes web, web_search_used)."""
    if openai_web_search_enabled():
        try:
            raw, sources, queries = identify_with_openai_web_search(
                instructions=_identification_system_prompt(use_web=True),
                user_input=user_prompt,
            )
            return raw, sources, queries, True
        except Exception as exc:
            logger.warning("[product_identification] recherche web OpenAI echouee: %s", exc)
    raw = _call_identification_llm(user_prompt, use_web=False)
    return raw, [], [], False


def identify_product(query: str) -> ProductIdentification:
    """
    Identifie et enrichit un produit a partir du nom ou d'une description courte.
    Ne retourne aucun code SH.
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

    user_prompt = (
        f"Description utilisateur :\n{original}\n\n"
        "Construis la fiche d'identification marchandise (sans code douanier)."
    )

    try:
        raw, web_sources, web_search_queries, web_search_used = _call_identification_with_optional_web(user_prompt)
    except Exception as exc:
        logger.warning("[product_identification] echec LLM: %s", exc)
        return ProductIdentification(
            original_query=original,
            enriched_description=original,
            product_name=original[:120],
            identification_confidence=25,
            skipped=True,
            skip_reason="llm_error",
            notes=str(exc),
        )

    parsed = _parse_identification_json(raw, fallback_query=original)
    enriched = str(parsed.get("enriched_description") or "").strip() or original
    notes = str(parsed.get("notes") or "").strip()
    if web_search_used and (web_sources or web_search_queries):
        notes = (notes + " Recherche internet OpenAI consultee.").strip()

    return ProductIdentification(
        original_query=original,
        product_name=str(parsed.get("product_name") or original[:120]).strip(),
        product_type=str(parsed.get("product_type") or "").strip(),
        function_usage=str(parsed.get("function_usage") or "").strip(),
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
        enriched_description=enriched,
        notes=notes,
        web_search_used=web_search_used,
        web_sources=web_sources,
        web_search_queries=web_search_queries,
    )


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
        "[prepare_query] identification DONE for '%s' -> product_type='%s', function='%s', enriched_len=%d",
        original[:40],
        identification.product_type[:40],
        identification.function_usage[:40],
        len(text),
    )
    return text, identification
