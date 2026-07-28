import glob
import faiss
import numpy as np
import pathlib
import requests
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any
from .config.settings import Config
from .openai_compat import chat_completion_kwargs
from .app_logger import get_logger
from dotenv import load_dotenv
import threading
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain_community.document_loaders import PyPDFLoader
from requests.auth import HTTPBasicAuth
from sqlalchemy import text as sql_text
from sqlalchemy.exc import OperationalError

from .db import get_db
import urllib3
import json
from openai import OpenAI
from .product_identification import (
    ProductIdentification,
    _identification_matches_reference,
    prepare_query_for_classification,
)
from .candidate_set_enforcer import (
    attach_candidates_to_classifications,
    format_merged_candidates_prompt,
    limit_position_candidates,
    rerank_candidates_by_affinity,
    retrieve_locked_tec_context,
    summarize_candidate_evidence,
)
from .tariff_labels import (
    find_positions_by_heading_match,
    find_positions_by_label_keywords,
    lookup_position_label,
)
from .classification_progress import ClassificationProgressReporter
from .functional_profile import build_functional_profile
from .product_evidence import build_product_evidence
from .telemetry import increment_telemetry, record_telemetry_call
from .structured_tariff_retrieval import search_structured_tariff_positions

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Nouveau client OpenAI (SDK >= 1.x)
client = OpenAI(api_key=Config.OPENAI_API_KEY)

logger = get_logger(__name__)

# --- Détection « question Mosam » par similarité (difflib), pas par explosion de variantes regex ---

# Seuil : assez bas pour tolérer fautes (ex. « fonateur »), assez haut pour éviter les faux positifs marchandise.
_META_FUZZY_GATE_WITH_MOSAM = 0.74
_META_FUZZY_GATE_NO_MOSAM = 0.82
_META_FUZZY_INTENT_MIN = 0.72
_META_FUZZY_FULL_FAQ_MIN = 0.78

# Phrases canoniques (ASCII, sans accents — aligné sur _normalize_text_for_meta_match).
_META_PHRASES_FULL_FAQ = [
    "informations completes sur mosam",
    "fiche complete mosam",
    "fiche mosam complete",
    "tout sur mosam",
    "aide complete mosam",
]
_META_PHRASES_FOUNDERS = [
    "fondateur mosam",
    "fondateurs mosam",
    "fondateur de mosam",
    "qui est le fondateur de mosam",
    "qui est le fondateur mosam",
    "qui sont les fondateurs de mosam",
    "qui a cree mosam",
    "cree par qui mosam",
    "par qui mosam",
    "par qui a cree mosam",
]
_META_PHRASES_RULES = [
    "regles d utilisation mosam",
    "regles mosam",
    "quelles sont les regles mosam",
    "utilisation de mosam",
]
_META_PHRASES_WORKS = [
    "comment mosam fonctionne",
    "comment fonctionne mosam",
    "how does mosam work",
]
_META_PHRASES_PURPOSE = [
    "mosam a ete cree pour",
    "pourquoi mosam",
    "pour quoi mosam",
    "a ete cree pour quoi mosam",
]
_META_PHRASES_HELP = [
    "comment mosam peut maider",
    "comment mosam peut m aider",
    "a quoi sert mosam",
    "mosam sert a quoi",
    "comment utiliser mosam",
    "how can mosam help",
    "what is mosam for",
]
_META_PHRASES_IDENTITY = [
    "qui est mosam",
    "quest ce que mosam",
    "qu est ce que mosam",
    "cest quoi mosam",
    "what is mosam",
    "who is mosam",
]
# Questions à l'assistant sans nommer Mosam (seuil plus strict).
_META_PHRASES_ASSISTANT_ONLY = [
    "qui es tu",
    "qui etes vous",
    "comment tu t appelles",
    "comment t appelles tu",
    "comment tu tappelles",
    "presente toi",
    "who are you",
]
# Politesse / bien-être (ton chaleureux, sans « mosam » dans le texte).
_META_PHRASES_ASSISTANT_WARMTH = [
    "ca va",
    "ca va bien",
    "tout va bien",
    "comment vas tu",
    "comment allez vous",
    "tu vas bien",
    "vous allez bien",
    "vous sentez vous bien",
    "how are you",
    "hope you are well",
]
# Âge et autres questions perso hors politesse — ton factuel.
_META_PHRASES_ASSISTANT_AGE = [
    "quel age as tu",
    "quelle age as tu",
    "tu as quel age",
    "quel est ton age",
    "quelle est ton age",
    "quel est votre age",
    "quelle est votre age",
    "how old are you",
    "t as quel age",
    "tas quel age",
]
_META_PHRASES_GATE_EXTRA = [
    "rapport avec mosam",
    "savoir sur mosam",
    "quest ce que je dois savoir sur mosam",
    "tout ce qui est en rapport avec mosam",
    "mosam a ete cree",
    "mosam a ete developpe",
    "cree par mosam",
    "how to use mosam",
    "what should i know about mosam",
]

# Toutes les formulations « question Mosam » pour le passage au court-circuit (évite de recalculer).
_META_ALL_GATE_PHRASES: list[str] = (
    _META_PHRASES_FULL_FAQ
    + _META_PHRASES_FOUNDERS
    + _META_PHRASES_RULES
    + _META_PHRASES_WORKS
    + _META_PHRASES_PURPOSE
    + _META_PHRASES_HELP
    + _META_PHRASES_IDENTITY
    + _META_PHRASES_GATE_EXTRA
)

_INTENT_PRECEDENCE = ("founders", "rules", "works", "purpose", "help", "identity")

# Demande de code / position sans description de produit (« Code HS pour Mosam ») → réponse courte, pas la fiche complète.
_META_HS_CODE_REQUEST_RE = re.compile(
    r"(?is)(?=.*\bmosam\b)(?=.*(?:\bcode\s+(?:hs|sh|tec)\b|\bhs\s+code\b|\btec\s*/\s*sh\b|"
    r"\bposition\s+tarifaire\b|\bclassement\s+tarifaire\b|\bnomenclature(?:\s+tarifaire)?\b))",
)

# « Mosam » comme marque / modèle (ex. « Téléphone Mosam », « Mosam smartphone 5G ») : pas question meta.
_META_PRODUCT_NEAR_MOSAM_RE = re.compile(
    r"(?is)"
    r"\b(?:telephones?|smartphones?|portables?|mobiles?|cellulaires?|"
    r"ordinateurs?|ordis?|pcs?|tablettes?|laptops?|notebooks?|"
    r"chargeurs?|ecrans?|ecouteurs?|casques?|souris?|claviers?|"
    r"routeurs?|modems?|box(?:es)?|\busb\b)\b.{0,55}\bmosam\b|"
    r"\bmosam\b.{0,55}\b(?:telephones?|smartphones?|portables?|mobiles?|cellulaires?|"
    r"ordinateurs?|ordis?|pcs?|tablettes?|laptops?|notebooks?|"
    r"chargeurs?|ecrans?|\b5g\b|\b4g\b|\blte\b|\bgb\b|\bram\b|\bgo\b)\b"
)

# « Mosam » comme dénomination sociale / bénéficiaire (pas question sur l’assistant).
# Ne pas confondre avec « pourquoi mosam » : \bpour\s+mosam\b n’aligne pas sur « pourquoi » (pas de coupure de mot).
_META_MOSAM_COMPANY_SUFFIX_RE = re.compile(
    r"(?is)\bmosam\s+(?:sa\b|sas\b|sarl\b|sarlu\b|sasu\b|eurl\b|sca\b|gie\b|ltd\b|inc\b|llc\b|plc\b|gmbh\b)",
)
_META_MOSAM_IMPORT_EXPORT_AND_GOODS_RE = re.compile(
    r"(?is)(?=.*\b(?:import|importation|export|exportation)\b)(?=.*\bmarchandises?\b)(?=.*\bmosam\b)"
)
_META_MOSAM_BENEFICIARY_POUR_RE = re.compile(r"(?is)\bpour\s+mosam\b")
# « pour Mosam » seul matche le fuzzy « pourquoi mosam » ; n’exempter du meta que si contexte logistique / douane.
_META_MOSAM_LOGISTICS_CONTEXT_RE = re.compile(
    r"(?is)\b(?:import|importation|export|exportation|marchandises?|livraison|expedition|"
    r"fret|conteneur|cargaison|colis|palette|douane|transit|dae|connaissement)\b"
)


def _meta_collapse_ws(s: str) -> str:
    # « as-tu » / tirets → espaces pour rapprocher les scores fuzzy des phrases canoniques.
    t = (s or "").replace("-", " ").strip().lower()
    return re.sub(r"\s+", " ", t)


def _meta_fuzzy_best_phrase_in_text(phrase: str, text: str) -> float:
    """
    Score dans [0,1] : correspondance entre une phrase de référence et le texte,
    avec fenêtres glissantes (tolère fautes de frappe et texte bruité autour).
    """
    p = _meta_collapse_ws(phrase)
    t = _meta_collapse_ws(text)
    if not p or not t:
        return 0.0
    if p in t:
        return 1.0
    pl = len(p)
    best = 0.0
    pad = 14
    step = 1 if len(t) < 220 else 2 if len(t) < 450 else 3
    # Fenêtres de longueur proche de la référence (fautes / mots en plus).
    for wl in range(max(5, pl - 6), min(len(t), pl + pad) + 1):
        for i in range(0, len(t) - wl + 1, step):
            win = t[i : i + wl]
            best = max(best, SequenceMatcher(None, p, win).ratio())
    if len(t) <= pl + pad:
        best = max(best, SequenceMatcher(None, p, t).ratio())
    return best


def _meta_text_chunks(normalized_raw: str) -> list[str]:
    """Découpe le texte normalisé : lignes + extrait autour de « mosam » + tout le texte court."""
    chunks: list[str] = []
    t = _meta_collapse_ws(normalized_raw)
    if not t:
        return chunks
    if len(t) <= 400:
        chunks.append(t)
    else:
        chunks.append(t[:500])
    for line in normalized_raw.splitlines():
        c = _meta_collapse_ws(line)
        if len(c) >= 4:
            chunks.append(c)
    if "mosam" in t:
        i = t.find("mosam")
        lo = max(0, i - 120)
        hi = min(len(t), i + 140)
        chunks.append(t[lo:hi])
    # Dédupliquer en gardant l'ordre
    seen: set[str] = set()
    out: list[str] = []
    for ch in chunks:
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return out


def _mosam_line_looks_like_product_brand(normalized_ascii: str) -> bool:
    """True si au moins une ligne ressemble à une désignation de produit + Mosam (marque), pas à une FAQ."""
    for line in normalized_ascii.splitlines():
        s = _meta_collapse_ws(line)
        if not s or "mosam" not in s or len(s) > 160:
            continue
        if _META_PRODUCT_NEAR_MOSAM_RE.search(s):
            return True
    return False


def _mosam_line_looks_like_company_or_customs_context(normalized_ascii: str) -> bool:
    """
    True si « Mosam » est plutôt société / destinataire / flux logistique que question sur l’outil.
    Évite les faux positifs fuzzy « pour … mosam » ≈ « pourquoi mosam ».
    """
    for line in normalized_ascii.splitlines():
        s = _meta_collapse_ws(line)
        if not s or "mosam" not in s:
            continue
        if _META_MOSAM_COMPANY_SUFFIX_RE.search(s):
            return True
        if _META_MOSAM_IMPORT_EXPORT_AND_GOODS_RE.search(s):
            return True
        if _META_MOSAM_BENEFICIARY_POUR_RE.search(s) and _META_MOSAM_LOGISTICS_CONTEXT_RE.search(s):
            return True
    return False


def _meta_best_pack_score(chunks: list[str], phrases: list[str]) -> float:
    best = 0.0
    for ch in chunks:
        for p in phrases:
            best = max(best, _meta_fuzzy_best_phrase_in_text(p, ch))
            if best >= 0.97:
                return best
    return best


_ASSISTANT_META_NARRATIVE = (
    "Je suis Mosam, assistant logiciel pour la classification tarifaire selon le TEC/SH CEDEAO.\n\n"
    "À quoi je sers : vous décrivez une ou plusieurs marchandises (matière, usage, caractéristiques "
    "techniques), ou vous envoyez un fichier txt ou pdf ; je propose des codes et taux indicatifs "
    "à partir de la documentation tarifaire et de l’analyse automatique du texte.\n\n"
    "Comment je peux vous aider : accélérer une première lecture tarifaire et présenter une réponse "
    "structurée ; toute utilisation officielle exige une validation humaine.\n\n"
    "Comment je fonctionne (synthèse) : recherche d’extraits pertinents dans la base tarifaire, "
    "puis génération d’une proposition (codes, sections, taux possibles). La qualité dépend surtout "
    "de la précision de votre description.\n\n"
    "Règles d’utilisation : décrire le produit le plus factuellement possible ; une ligne ou une puce "
    "par article si vous en avez plusieurs ; traiter toute proposition comme indicative et à faire "
    "valider avant toute utilisation officielle.\n\n"
    "Pourquoi Mosam existe dans ce contexte : pour faciliter le travail de première analyse de "
    "classification à partir des textes officiels CEDEAO.\n\n"
    "Mosam a été créé par l’Industrie Mosam, avec pour fondateurs Mohamed Ndiaye et "
    "Christophe Ouattara."
)

_META_ASSISTANT_JSON = json.dumps(
    {
        "narrative": _ASSISTANT_META_NARRATIVE,
        "classifications": [],
        "assistant_info": True,
    },
    ensure_ascii=False,
)

# Réponse fixe complète (rétrocompat / défaut si question très générale).
ASSISTANT_META_RESPONSE_JSON: str = _META_ASSISTANT_JSON

_META_MORE_HINT = (
    "\n\nPour afficher toute la fiche Mosam d’un coup (rôle, fonctionnement, règles, équipe), "
    "écrivez par exemple : « Informations complètes sur Mosam »."
)

_META_SNIPPET_FOUNDERS = (
    "Les fondateurs de Mosam sont Mohamed Ndiaye et Christophe Ouattara. "
    "Mosam a été créé par l’Industrie Mosam."
)
_META_SNIPPET_RULES = (
    "Règles d’utilisation : décrire la marchandise de façon factuelle (matière, usage, caractéristiques) ; "
    "une ligne ou une puce par article si vous en avez plusieurs ; traiter chaque proposition comme "
    "indicative et à faire valider avant toute utilisation officielle."
)
_META_SNIPPET_WORKS = (
    "Mosam repère des extraits pertinents dans la base tarifaire, puis produit une proposition structurée "
    "(codes, sections, taux possibles). La qualité dépend surtout de la précision de votre description."
)
_META_SNIPPET_PURPOSE = (
    "Mosam vise à faciliter la première analyse de classification tarifaire selon le TEC/SH CEDEAO, "
    "à partir des textes officiels. Les propositions restent indicatives."
)
_META_SNIPPET_HELP = (
    "Mosam vous aide à obtenir plus vite une proposition de codes et de taux possibles : décrivez la "
    "marchandise dans le champ prévu ou envoyez un fichier txt ou pdf. La décision définitive revient "
    "à l’utilisateur ou à son référent métier."
)
_META_SNIPPET_IDENTITY = (
    "Je m’appelle Mosam. Je suis un assistant logiciel pour la classification tarifaire TEC/SH CEDEAO. "
    "Je ne suis pas une personne physique ; j’aide les équipes à formuler des propositions indicatives "
    "de classement tarifaire."
)
_META_SNIPPET_WARMTH = (
    "Merci de prendre des nouvelles : tout va bien de mon côté, et j’espère sincèrement que vous allez bien "
    "vous aussi. Je suis là pour vous accompagner sur la classification tarifaire TEC/SH CEDEAO — "
    "décrivez une marchandise quand vous êtes prêt, ou posez une question qui contient « Mosam » si vous "
    "voulez en savoir plus sur l’outil."
)
_META_SNIPPET_PERSONAL = (
    "Je suis un programme informatique : je n’ai pas d’âge ni de vie personnelle au sens humain. "
    "Mosam sert à proposer des classements tarifaires indicatifs (TEC/SH CEDEAO). "
    "Décrivez une marchandise dans le champ prévu, ou posez une question qui contient le mot « Mosam » "
    "pour obtenir une réponse sur l’outil."
)
_META_SNIPPET_UNKNOWN = (
    "Je n’ai pas de réponse dédiée à cette question précise dans Mosam. "
    "Pour des codes TEC/SH indicatifs, décrivez une marchandise ou envoyez un fichier txt ou pdf. "
    "Pour tout ce qui dépasse la classification tarifaire (juridique, sécurité, organisation, comptes, etc.), "
    "adressez-vous à votre administration ou à votre référent métier.\n\n"
    "Pour un rappel général sur mon rôle et mon fonctionnement, vous pouvez écrire par exemple : "
    "« Informations complètes sur Mosam »."
)
_META_SNIPPET_HS_GUIDE = (
    "Pour obtenir un code TEC/SH indicatif, décrivez la marchandise dans le champ prévu "
    "(matière, usage, caractéristiques techniques) ou envoyez un fichier txt ou pdf. "
    "Ici, « Mosam » est le nom de cet assistant logiciel, pas une désignation de produit : sans description "
    "concrète de marchandise, je ne peux pas proposer de position tarifaire. "
    "Toute proposition reste indicative et doit être validée avant toute utilisation officielle."
)
_META_MORE_HINT_COMPACT = (
    "\n\nPour afficher toute la fiche Mosam (rôle, fonctionnement, règles, équipe), écrivez par exemple : "
    "« Informations complètes sur Mosam »."
)


def build_assistant_meta_response_json(query: str) -> str:
    """
    Réponse assistant_info : courte si la question est ciblée, fiche complète si question large
    ou si l'utilisateur demande explicitement la fiche complète.
    Intentions choisies par score de similarité (difflib), pas par regex à variantes.
    """
    t = _normalize_text_for_meta_match(query or "")
    if not t:
        return _META_ASSISTANT_JSON
    chunks = _meta_text_chunks(t)
    collapsed = _meta_collapse_ws(t)
    # Sans « mosam » dans le texte : questions à l'assistant (nom, présentation) ne doivent pas
    # retomber sur la fiche complète — les scores fuzzy sur un long copier-collé d'UI restent souvent < seuil.
    if "mosam" not in collapsed:
        score_id = _meta_best_pack_score(chunks, _META_PHRASES_ASSISTANT_ONLY)
        score_age = _meta_best_pack_score(chunks, _META_PHRASES_ASSISTANT_AGE)
        score_warm = _meta_best_pack_score(chunks, _META_PHRASES_ASSISTANT_WARMTH)
        if max(score_id, score_age, score_warm) >= _META_FUZZY_GATE_NO_MOSAM:
            best = max(score_id, score_age, score_warm)
            # En cas d’égalité ou quasi-égalité, priorité : chaleur > âge > identité.
            if score_warm >= best - 0.02 and score_warm >= score_age - 0.02 and score_warm >= score_id - 0.02:
                narrative = _META_SNIPPET_WARMTH + _META_MORE_HINT
            elif score_age > score_id:
                narrative = _META_SNIPPET_PERSONAL + _META_MORE_HINT
            else:
                narrative = _META_SNIPPET_IDENTITY + _META_MORE_HINT
            return json.dumps(
                {"narrative": narrative, "classifications": [], "assistant_info": True},
                ensure_ascii=False,
            )
    # Avant le fuzzy « fiche complète » : un collage UI peut sinon atteindre le seuil et masquer cette intention.
    if "mosam" in collapsed and _META_HS_CODE_REQUEST_RE.search(collapsed):
        return json.dumps(
            {
                "narrative": _META_SNIPPET_HS_GUIDE + _META_MORE_HINT_COMPACT,
                "classifications": [],
                "assistant_info": True,
            },
            ensure_ascii=False,
        )

    if _meta_best_pack_score(chunks, _META_PHRASES_FULL_FAQ) >= _META_FUZZY_FULL_FAQ_MIN:
        return _META_ASSISTANT_JSON

    scores: dict[str, float] = {
        "founders": _meta_best_pack_score(chunks, _META_PHRASES_FOUNDERS),
        "rules": _meta_best_pack_score(chunks, _META_PHRASES_RULES),
        "works": _meta_best_pack_score(chunks, _META_PHRASES_WORKS),
        "purpose": _meta_best_pack_score(chunks, _META_PHRASES_PURPOSE),
        "help": _meta_best_pack_score(chunks, _META_PHRASES_HELP),
        "identity": _meta_best_pack_score(chunks, _META_PHRASES_IDENTITY),
    }
    qualified = {k: v for k, v in scores.items() if v >= _META_FUZZY_INTENT_MIN}
    if not qualified:
        # Question reconnue comme « à propos de Mosam » mais sans intention ciblée : pas d’invention, réponse honnête.
        return json.dumps(
            {
                "narrative": _META_SNIPPET_UNKNOWN,
                "classifications": [],
                "assistant_info": True,
            },
            ensure_ascii=False,
        )
    best = max(qualified.values())
    near = [k for k, v in qualified.items() if v >= best - 0.04]
    intent: str | None = None
    for k in _INTENT_PRECEDENCE:
        if k in near:
            intent = k
            break
    if intent is None:
        intent = max(qualified, key=qualified.get)

    narrative_map = {
        "founders": _META_SNIPPET_FOUNDERS,
        "rules": _META_SNIPPET_RULES,
        "works": _META_SNIPPET_WORKS,
        "purpose": _META_SNIPPET_PURPOSE,
        "help": _META_SNIPPET_HELP,
        "identity": _META_SNIPPET_IDENTITY,
    }
    narrative = narrative_map[intent] + _META_MORE_HINT
    return json.dumps(
        {"narrative": narrative, "classifications": [], "assistant_info": True},
        ensure_ascii=False,
    )


def _normalize_text_for_meta_match(text: str) -> str:
    """
    Applatit les apostrophes typographiques (U+2019, etc.) avant NFKD/ASCII.
    Sinon « Qu'est-ce » devient « Quest-ce » et ne matche plus les motifs qu'est…
    """
    t = text
    for ch in (
        "\u2019",  # right single quotation mark (courant dans les UI / Word)
        "\u2018",  # left single quotation mark
        "\u02bc",  # modifier letter apostrophe
        "\u02bb",
    ):
        t = t.replace(ch, "'")
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")
    return t


def is_assistant_meta_query(text: str) -> bool:
    """True si le texte ressemble à une question sur Mosam / l'assistant (score de similarité)."""
    if not (text or "").strip():
        return False
    t = _normalize_text_for_meta_match(text)
    if not t:
        return False
    collapsed = _meta_collapse_ws(t)
    if "mosam" in collapsed and _mosam_line_looks_like_product_brand(t):
        return False
    if "mosam" in collapsed and _mosam_line_looks_like_company_or_customs_context(t):
        return False
    chunks = _meta_text_chunks(t)
    if "mosam" in collapsed:
        return _meta_best_pack_score(chunks, _META_ALL_GATE_PHRASES) >= _META_FUZZY_GATE_WITH_MOSAM
    score_id = _meta_best_pack_score(chunks, _META_PHRASES_ASSISTANT_ONLY)
    score_age = _meta_best_pack_score(chunks, _META_PHRASES_ASSISTANT_AGE)
    score_warm = _meta_best_pack_score(chunks, _META_PHRASES_ASSISTANT_WARMTH)
    return max(score_id, score_age, score_warm) >= _META_FUZZY_GATE_NO_MOSAM


# Configuration embeddings / modèles
# Par défaut: "small" (moins cher + rapide). Tu peux override via Config.EMBEDDING_MODEL
EMBEDDING_MODEL = getattr(Config, "EMBEDDING_MODEL", None) or "text-embedding-3-small"


def _embed_texts_openai(texts: list[str], *, batch_size: int = 128) -> list[list[float]]:
    """Embeddings OpenAI en batch pour éviter les limites de requête."""
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=chunk)
        out.extend([d.embedding for d in resp.data])
    return out


def _embedding_dim_probe() -> int:
    """Retourne la dimension du modèle d'embeddings courant."""
    vecs = _embed_texts_openai(["dim_probe"], batch_size=1)
    return len(vecs[0])

def save_chunks(chunks, filepath):
    """Sauvegarder les chunks dans un fichier JSON."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump([doc.page_content for doc in chunks], f, indent=4)

def load_chunks(filepath):
    """Charger les chunks à partir d'un fichier JSON."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = json.load(f)
    return [Document(page_content=chunk) for chunk in content]

# Load documents and create FAISS index
def load_documents_and_create_chunks():
    """Charger les documents, les traduire et les diviser en chunks."""
    
    # Obtenir le répertoire du fichier rag.py
    rag_dir = os.path.dirname(os.path.abspath(__file__))
    chunks_filepath = os.path.join(rag_dir, "chunks.json")
    
    if os.path.exists(chunks_filepath):
        logger.info("Chargement des chunks à partir du fichier.")
        chunks = load_chunks(chunks_filepath)
        logger.info("%s chunks charges depuis le fichier", len(chunks))
        return chunks

    documents = []
    logger.debug("start load doc in document")
    
    contrat_dir = os.path.join(rag_dir, "contrat")
    
    # Vérifier que le dossier existe
    if not os.path.exists(contrat_dir):
        raise FileNotFoundError(f"Le dossier 'contrat' n'existe pas! Chemin recherche: {contrat_dir}")
    
    # Vérifier qu'il y a des fichiers PDF
    pdf_files = glob.glob(os.path.join(contrat_dir, "*.pdf"))
    if not pdf_files:
        raise FileNotFoundError("Aucun fichier PDF trouve dans le dossier 'contrat'!")
    
    logger.info("%s fichiers PDF trouves", len(pdf_files))
    
    for file in pdf_files:
        try:
            logger.debug("Chargement de %s...", file)
            loader = PyPDFLoader(file)
            documents += loader.load()
        except Exception as e:
            logger.error("Erreur lors du chargement du fichier '%s': %s", file, e)
    
    if not documents:
        raise ValueError("Aucun document n'a pu etre charge!")
    
    logger.info("%s documents charges", len(documents))
    logger.debug("finish load doc in document")
    logger.debug("start the translate")
    logger.debug("finish the translate")
    
    # Diviser les documents en chunks
    logger.debug("start the splitting of the text")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600, 
        chunk_overlap=120, 
        length_function=len, 
        separators=["\n\n", "\n", "."]
    )
    chunks = text_splitter.split_documents(documents=documents)
    
    if not chunks:
        raise ValueError("Aucun chunk cree apres le splitting!")
    
    logger.info("%s chunks crees", len(chunks))
    logger.debug("finish the splitting of the text")
    
    save_chunks(chunks, chunks_filepath)
    return chunks

def initialize_chatbot():
    faiss.omp_set_num_threads(3)
    # Obtenir le répertoire du fichier rag.py
    rag_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(rag_dir, "indexFaiss", "local_index.faiss")
    
    # Toujours créer les chunks
    logger.debug("start loading document and create chunks")
    chunks = load_documents_and_create_chunks()
    
    if not chunks:
        raise ValueError("Aucun chunk disponible!")
    
    logger.info("%s chunks disponibles", len(chunks))
    logger.debug("finish loading document and create chunks")

    index: faiss.Index
    expected_dim = _embedding_dim_probe()

    if os.path.exists(index_path):
        # Charger l'index directement depuis le fichier FAISS (chemin pre-bâti)
        index = faiss.read_index(index_path)
        logger.info(
            "Index charge depuis le fichier existant (%s vecteurs, dim=%s)",
            index.ntotal,
            index.d,
        )

        # Si l'index a été créé avec un autre modèle (HF vs OpenAI), on le reconstruit.
        if index.d != expected_dim or int(index.ntotal) != len(chunks):
            logger.warning(
                "Index FAISS incompatible avec le modèle d'embeddings courant (index.d=%s expected_dim=%s ntotal=%s chunks=%s). Reconstruction...",
                index.d,
                expected_dim,
                index.ntotal,
                len(chunks),
            )
            index = create_faiss_index(chunks, expected_dim=expected_dim)
    else:
        # Créer un nouvel index en utilisant les embeddings OpenAI
        logger.debug("start the creation of the faiss index (OpenAI embeddings)")
        index = create_faiss_index(chunks, expected_dim=expected_dim)
        logger.debug("finish the creation of the faiss index")

    return chunks, index


def create_faiss_index(chunks, *, expected_dim: int | None = None):
    """Créer un index FAISS à partir des chunks."""
    
    # VÉRIFICATIONS CRITIQUES
    if not chunks:
        raise ValueError("Liste de chunks vide!")
    
    logger.info("Generation des embeddings OpenAI pour %s chunks...", len(chunks))
    
    # Extraire le texte des chunks
    chunk_texts = [chunk.page_content for chunk in chunks]
    
    # Vérifier qu'il y a du contenu
    if not chunk_texts or not chunk_texts[0]:
        raise ValueError("Les chunks ne contiennent pas de texte!")
    
    logger.debug(
        "Premier chunk (100 premiers caracteres): %s...",
        chunk_texts[0][:100],
    )
    
    # Générer les embeddings via l'API OpenAI (batch)
    try:
        chunk_vectors = _embed_texts_openai(chunk_texts)
    except Exception as e:
        logger.exception("Generation des embeddings OpenAI a échoué")
        raise
    
    # Vérifier que les embeddings ont été générés
    if not chunk_vectors or len(chunk_vectors) == 0:
        raise ValueError("Aucun embedding genere!")
    
    logger.info("%s embeddings generes", len(chunk_vectors))
    dim = len(chunk_vectors[0])
    logger.info("Dimension des embeddings: %s", dim)
    if expected_dim is not None and dim != expected_dim:
        raise ValueError(f"Dimension embeddings inattendue: {dim} (attendu {expected_dim})")
    
    # Convertir en array numpy
    chunk_vectors_array = np.array(chunk_vectors).astype('float32')
    
    # Créer l'index FAISS
    dimension = chunk_vectors_array.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(chunk_vectors_array)
    
    logger.info("Index FAISS cree avec %s vecteurs", index.ntotal)
    
    # Obtenir le répertoire du fichier rag.py
    rag_dir = os.path.dirname(os.path.abspath(__file__))
    index_dir = os.path.join(rag_dir, "indexFaiss")
    
    # Créer le dossier si nécessaire
    os.makedirs(index_dir, exist_ok=True)
    
    # Sauvegarder l'index
    index_path = os.path.join(index_dir, "local_index.faiss")
    faiss.write_index(index, index_path)
    logger.info("Index sauvegarde dans '%s'", index_path)
    
    return index


_CLASSIFICATIONS_INDEX_LOCK = threading.Lock()


def _classifications_index_paths() -> tuple[str, str]:
    rag_dir = os.path.dirname(os.path.abspath(__file__))
    index_dir = os.path.join(rag_dir, "indexFaiss")
    os.makedirs(index_dir, exist_ok=True)
    index_path = os.path.join(index_dir, "validated_classifications.faiss")
    meta_path = os.path.join(index_dir, "validated_classifications_meta.json")
    return index_path, meta_path


def _classification_example_to_text(example: dict[str, object]) -> str:
    """
    Texte concis pour embeddings: on encode surtout les champs "métier"
    qui relient une description à un HS.
    """
    desc = str(example.get("description_produit") or "").strip()
    code = str(example.get("code_tarifaire") or "").strip()
    section = str(example.get("section_produit") or "").strip()
    chapter = str(example.get("chapitre_produit") or "").strip()
    origin = str(example.get("origin") or "").strip()
    value = str(example.get("value") or "").strip()
    dd = str(example.get("dd_rate") or "").strip()
    rs = str(example.get("rs_rate") or "").strip()
    other = str(example.get("other_taxes") or "").strip()
    unit = str(example.get("us_unit") or "").strip()
    confidence = example.get("classification_confidence")

    parts = [
        f"description={desc}",
        f"hs_code={code}",
        f"section={section}",
        f"chapter={chapter}",
        f"origin={origin}",
        f"value={value}",
        f"dd={dd}",
        f"rs={rs}",
        f"other_taxes={other}",
        f"unit={unit}",
    ]
    if confidence is not None:
        parts.append(f"confidence={confidence}")
    return " | ".join([p for p in parts if p])


def _persist_classifications_index(index: faiss.Index, meta: list[dict[str, object]]) -> None:
    index_path, meta_path = _classifications_index_paths()
    faiss.write_index(index, index_path)
    tmp_path = meta_path + ".tmp"

    # Convertit les champs non sérialisables (ex: UUID/Decimal/Datetime) en string.
    def _jsonify(obj: object) -> object:
        try:
            import uuid as _uuid

            if isinstance(obj, _uuid.UUID):
                return str(obj)
        except Exception:
            pass

        try:
            import datetime as _dt

            if isinstance(obj, (_dt.datetime, _dt.date, _dt.time)):
                return obj.isoformat()
        except Exception:
            pass

        try:
            import decimal as _decimal

            if isinstance(obj, _decimal.Decimal):
                return str(obj)
        except Exception:
            pass

        if isinstance(obj, dict):
            return {k: _jsonify(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_jsonify(v) for v in obj]
        return obj

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(_jsonify(meta), f, ensure_ascii=False, indent=2)

    # Remplacement atomique (evite meta JSON partiellement ecrits).
    os.replace(tmp_path, meta_path)


def _empty_validated_classifications_index() -> tuple[faiss.Index, list[dict[str, object]]]:
    return faiss.IndexFlatL2(_embedding_dim_probe()), []


def _load_classifications_index_from_disk() -> tuple[faiss.Index, list[dict[str, object]]]:
    index_path, meta_path = _classifications_index_paths()
    expected_dim = _embedding_dim_probe()
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        # Si des fichiers d'apprentissage ont ete supprimes/corrompus, on reconstruit
        # depuis la DB plutot que repartir a vide.
        try:
            return _rebuild_classifications_index_from_db()
        except OperationalError as exc:
            logger.warning(
                "[validated_classifications] DB indisponible au demarrage, index vide: %s",
                exc,
            )
            return _empty_validated_classifications_index()

    index = faiss.read_index(index_path)
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta: list[dict[str, object]] = json.load(f)
    except Exception:
        # Peut arriver si écriture interrompue (ex: erreur de sérialisation précédente).
        logger.warning(
            "[validated_classifications] meta json invalide/corrompu, reconstruction depuis DB...",
            exc_info=True,
        )
        try:
            return _rebuild_classifications_index_from_db()
        except OperationalError as exc:
            logger.warning(
                "[validated_classifications] DB indisponible, index vide: %s",
                exc,
            )
            return _empty_validated_classifications_index()

    if index.d != expected_dim or int(index.ntotal) != len(meta):
        logger.warning(
            "[validated_classifications] index incompatible, reconstruction requise (index.d=%s expected_dim=%s ntotal=%s meta_len=%s)",
            index.d,
            expected_dim,
            index.ntotal,
            len(meta),
        )
        try:
            return _rebuild_classifications_index_from_db()
        except OperationalError as exc:
            logger.warning(
                "[validated_classifications] DB indisponible, index vide: %s",
                exc,
            )
            return _empty_validated_classifications_index()

    return index, meta


def _rebuild_classifications_index_from_db() -> tuple[faiss.Index, list[dict[str, object]]]:
    expected_dim = _embedding_dim_probe()
    index_path, meta_path = _classifications_index_paths()

    with get_db() as db:
        rows = db.execute(
            sql_text(
                """
                select
                  id::text as id,
                  description_produit,
                  section_produit,
                  chapitre_produit,
                  code_tarifaire,
                  classification_confidence,
                  quantity,
                  dd_rate,
                  rs_rate,
                  other_taxes,
                  us_unit,
                  origin,
                  value,
                  statut_validation
                from public.classifications
                where statut_validation = 'validé'
                order by created_at asc
                """
            )
        ).mappings().all()

    if not rows:
        empty = faiss.IndexFlatL2(expected_dim)
        _persist_classifications_index(empty, [])
        return empty, []

    examples: list[dict[str, object]] = [dict(r) for r in rows]
    texts = [_classification_example_to_text(ex) for ex in examples]
    vectors = _embed_texts_openai(texts)

    if not vectors:
        empty = faiss.IndexFlatL2(expected_dim)
        _persist_classifications_index(empty, [])
        return empty, []

    dim = len(vectors[0])
    if dim != expected_dim:
        # Très rare: embeddings model change. Reconstruction.
        raise ValueError(f"Dimension embeddings inattendue: {dim} (attendu {expected_dim})")

    vectors_array = np.array(vectors).astype("float32")
    index = faiss.IndexFlatL2(vectors_array.shape[1])
    index.add(vectors_array)
    _persist_classifications_index(index, examples)
    logger.info(
        "[validated_classifications] index reconstruit: vecteurs=%s meta_len=%s index_path=%s",
        index.ntotal,
        len(examples),
        index_path,
    )
    return index, examples


def initialize_validated_classifications_index() -> tuple[faiss.Index, list[dict[str, object]]]:
    """
    Charge un index FAISS dédié aux classifications validées.
    Si l'index n'existe pas ou est incompatible: reconstruction depuis la DB.
    """
    return _load_classifications_index_from_disk()


def add_validated_classification_example_to_index(
    classification_row: dict[str, object],
    *,
    index: faiss.Index,
    meta: list[dict[str, object]],
) -> None:
    """
    Ajoute un nouvel exemple validé à l'index (incremental add + persistance).
    """
    with _CLASSIFICATIONS_INDEX_LOCK:
        if classification_row.get("statut_validation") not in (None, "validé"):
            return

        if index is None:
            expected_dim = _embedding_dim_probe()
            index = faiss.IndexFlatL2(expected_dim)

        text = _classification_example_to_text(classification_row)
        vectors = _embed_texts_openai([text], batch_size=1)
        if not vectors:
            return

        vector = np.array([vectors[0]]).astype("float32")
        index.add(vector)
        # Stocke un meta minimal (et gardé aligné avec l'ordre des vectors).
        stored = dict(classification_row)
        meta.append(stored)
        _persist_classifications_index(index, meta)


def build_validated_examples_context(
    query: str,
    validated_index: faiss.Index | None,
    validated_meta: list[dict[str, object]] | None,
    *,
    k: int = 3,
) -> str:
    if not validated_index or validated_meta is None or len(validated_meta) == 0:
        return ""
    if getattr(validated_index, "ntotal", 0) <= 0:
        return ""

    k = max(1, int(k))
    indices, _ = search_faiss_index(query, validated_index, k=k)
    # `indices` est souvent un tableau numpy 2D (shape: [1, k]) => éviter `if not indices`.
    if indices is None:
        return ""
    if hasattr(indices, "size") and getattr(indices, "size") == 0:
        return ""
    if isinstance(indices, (list, tuple)) and len(indices) == 0:
        return ""

    snippets: list[str] = []
    for idx in indices[0]:
        if idx is None or int(idx) < 0:
            continue
        if int(idx) >= len(validated_meta):
            continue
        ex = validated_meta[int(idx)]
        desc = str(ex.get("description_produit") or "").strip()
        code = str(ex.get("code_tarifaire") or "").strip()
        section = str(ex.get("section_produit") or "").strip()
        chapter = str(ex.get("chapitre_produit") or "").strip()
        dd = str(ex.get("dd_rate") or "").strip()
        rs = str(ex.get("rs_rate") or "").strip()
        if not code:
            continue
        snippets.append(
            f"- {desc} => {code} ({section} / {chapter}), dd={dd}, rs={rs}"
        )

    if not snippets:
        return ""
    return "Exemples validés similaires:\n" + "\n".join(snippets)


def search_faiss_index(query, index, k=None):
    if k is None:
        k = max(1, int(getattr(Config, "MOSAM_FAISS_TOP_K", 20)))
    logger.debug("start vectorisation de la requete (OpenAI embeddings)")
    try:
        query_vec = _embed_texts_openai([query], batch_size=1)[0]
        query_vector = np.array(query_vec).astype("float32")
    except Exception as e:
        logger.exception("Embedding de la requete a échoué")
        raise
    logger.debug("finish vectorisation de la requete")
    logger.debug("start research of index by similarity")
    distances, indices = index.search(np.array([query_vector]), k)
    logger.debug("finish research of index by similarity")
    return indices, distances

# Use the LLM API
def _repair_truncated_json(text: str) -> str:
    """Tente de réparer un JSON tronqué par max_tokens.

    Stratégie : fermer les crochets/accolades manquants pour que
    json.loads puisse parser au moins la structure partielle.
    """
    import json as _json

    text = (text or "").strip()
    if not text:
        return '{"narrative":"Reponse tronquee","classifications":[]}'

    try:
        _json.loads(text)
        return text
    except Exception:
        pass

    open_braces = text.count("{") - text.count("}")
    open_brackets = text.count("[") - text.count("]")

    repaired = text.rstrip(", \n\r\t")
    repaired += "]" * max(open_brackets, 0)
    repaired += "}" * max(open_braces, 0)

    try:
        _json.loads(repaired)
        return repaired
    except Exception:
        return '{"narrative":"Reponse tronquee par le modele","classifications":[]}'


def _classification_model_routing_policy() -> str:
    policy = (getattr(Config, "MOSAM_CLASSIFICATION_MODEL_ROUTING", "") or "off").strip().lower()
    if policy in {"off", "auto"}:
        return policy
    return "off"


def _should_use_cheap_classification_model(prompt_text: str) -> bool:
    """Route les cas simples vers un modele moins couteux."""
    if _classification_model_routing_policy() != "auto":
        return False
    cheap_model = (getattr(Config, "MOSAM_CLASSIFICATION_MODEL_CHEAP", "") or "").strip()
    if not cheap_model:
        return False

    text = (prompt_text or "").strip()
    if not text:
        return False

    max_chars = max(1000, int(getattr(Config, "MOSAM_CLASSIFICATION_ROUTING_MAX_PROMPT_CHARS", 20000)))
    merchandise_blocks = len(re.findall(r"\[MARCHANDISE\s+\d+\]", text, flags=re.IGNORECASE))
    complexity_markers = (
        "produit 2",
        "produit 3",
        "marchandise 2",
        "marchandise 3",
    )

    lowered = text.lower()
    if len(text) > max_chars:
        return False
    if merchandise_blocks > 1:
        return False
    if any(marker in lowered for marker in complexity_markers):
        return False

    return True


def _classification_max_tokens(prompt_text: str) -> int:
    configured = max(800, int(getattr(Config, "MOSAM_CLASSIFICATION_MAX_OUTPUT_TOKENS", 4096)))
    merchandise_blocks = len(re.findall(r"\[MARCHANDISE\s+\d+\]", prompt_text or "", flags=re.IGNORECASE))
    item_count = max(1, merchandise_blocks)
    dynamic_cap = min(configured, max(1400, item_count * 1000))
    return max(800, dynamic_cap)


def _select_classification_model(prompt_text: str) -> str:
    cheap_model = (getattr(Config, "MOSAM_CLASSIFICATION_MODEL_CHEAP", "") or "").strip()
    default_model = Config.MOSAM_CLASSIFICATION_MODEL or "gpt-5"
    if cheap_model and _should_use_cheap_classification_model(prompt_text):
        return cheap_model
    return default_model


_CLASSIFICATION_OUTPUT_CONTRACT = (
    "Retourne exclusivement un objet JSON sans texte hors JSON. "
    "L'objet racine contient narrative (texte indicatif avec rappel de validation officielle) "
    "et classifications (tableau avec exactement une entree par produit). "
    "Chaque classification contient les champs description, hs_code, section, section_name, "
    "chapter, chapter_name, justification, excerpt, origin, value, confidence et "
    "classification_status. hs_code doit etre un code TEC numerique justifie par les candidats "
    "et les regles; il ne doit jamais etre vide. Si la sous-position exacte n'est pas certaine, "
    "retourne au minimum la position a 4 chiffres (ex. 84.71) au lieu d'un champ vide. "
    "N'utilise aucun code d'exemple ou code par defaut. confidence est un entier "
    "de 0 a 100 et classification_status vaut confirmee ou provisoire. "
    "narrative tient en une phrase. justification tient en trois phrases courtes (450 caracteres max) "
    "et resume seulement les RGI appliquees, la position retenue et la principale alternative ecartee. "
    "excerpt est limite a 160 caracteres. Le moteur local construit ensuite le rapport juridique detaille."
)


def _build_heading_hint_phrases(
    product_type: str,
    function_usage: str,
    family: str = "",
) -> list[str]:
    """Generic family-to-heading hints used only for retrieval, never as final codes."""
    combined = f"{product_type} {function_usage} {family}".lower()
    hints: list[str] = []
    if any(term in combined for term in ["tablet", "tablette", "portable tablet", "hybrid data processing"]):
        hints.extend([
            "machines automatiques de traitement de l information portatives",
            "machines automatiques de traitement de l information et leurs unites",
        ])
    if any(term in combined for term in ["storage array", "baie de stockage", "storage system", "unite de stockage"]):
        hints.extend([
            "machines automatiques de traitement de l information et leurs unites",
            "unites de memoire et de stockage de donnees",
        ])
    if any(term in combined for term in ["server computer", "serveur informatique", "rack server", "compute server"]):
        hints.extend([
            "machines automatiques de traitement de l information et leurs unites",
            "autres unites de machines automatiques de traitement de l information",
        ])
    if any(term in combined for term in ["accelerator", "gpu pcie", "pcie card", "expansion card", "carte acceleratrice"]):
        hints.extend([
            "parties et accessoires des machines du numero 84 71",
            "autres unites de machines automatiques de traitement de l information",
        ])
    if any(term in combined for term in ["ip camera", "camera thermique", "camera numerique", "multispectral", "imaging camera"]):
        hints.extend([
            "cameras de television appareils photographiques numeriques et camescopes",
            "appareils d emission pour la radiodiffusion ou la television",
        ])
    if any(term in combined for term in ["variateur", "frequency drive", "variable speed drive", "convertisseur statique", "vfd"]):
        hints.append(
            "transformateurs electriques convertisseurs electriques statiques redresseurs par exemple"
        )
    if any(term in combined for term in ["mixed reality", "realite mixte", "virtual reality", "display headset", "head mounted display"]):
        hints.extend([
            "moniteurs et projecteurs n incorporant pas d appareils de reception de television",
            "autres moniteurs et appareils d affichage video",
        ])
    return hints


def use_llm(prompt_text):
    model = ""
    started = time.perf_counter()
    try:
        system_instruction = (
            "Tu es Mosam, un assistant logiciel pour la classification tarifaire TEC/SH CEDEAO. "
            "Regles generales d'interpretation (RGI) — ordre obligatoire : "
            "RGI 1 (position decrivant directement le produit + Notes legales) ; "
            "RGI 2 a (incomplet/demonte/non monte) ; RGI 2 b (melange de matieres → conflit possible) ; "
            "RGI 3 uniquement si plusieurs positions restent possibles : 3 a plus specifique, 3 b caractere essentiel "
            "(assortiment ou produit integre, jamais sur simple % matiere), 3 c dernier recours numerique ; "
            "RGI 4 analogie en dernier recours ; RGI 5 emballages/etuis seulement ; RGI 6 sous-position. "
            "Le post-traitement Mosam applique ce pipeline : ne decompose pas un assortiment en lignes separees. "
            "Réponds uniquement aux questions posées. Priorise la clarté et la concision. "
            "Ne mentionne jamais les documents sources; fais comme si les infos étaient internes. "
            "Réponds dans la langue du prompt. "
            "Règles de sortie strictes: "
            "1) Une ligne de classification = un produit distinct demandé par l'utilisateur. Ne décompose jamais un produit en ses composants (écran, processeur, RAM, cuir, coton, polyester, doublure, fermeture, dimensions, etc.) sauf si l'utilisateur demande explicitement des lignes séparées pour des composants. "
            "1bis) Si la description contient des sections Composition ou Caractéristiques (% matières, doublure, poignée, dimensions), ce sont des précisions du même article — retourne une seule classification pour l'article principal (ex. sac à main chapitre 42), pas une ligne par matière. "
            "1ter) Si le libellé TEC ou les notes du chapitre indiquent un critère de sous-position (ex. matière de la surface extérieure, "
            "type de contenant, fonction déterminante) et que cette information n'est pas précisée dans la description, "
            "indique clairement dans la justification que la sous-position ne peut pas être déterminée avec certitude, "
            "retourne uniquement la position à 4 chiffres (sans code à 8 ou 10 chiffres), ne cite pas de sous-positions précises "
            "qui dépendent de ce critère manquant, baisse la confiance (≤ 65), et demande l'information manquante au lieu d'inventer un code. "
            "Ne cite une RGI que si elle est réellement appliquée (ex. ne pas invoquer RGI 3 si le critère de sous-position manque). "
            "2) Si l'utilisateur demande N produits (ex: « Produit 1: ordinateur, Produit 2: chargeur »), retourne au plus N lignes, une par produit. "
            "3) Pour un mélange (ex: mix de fruits secs), propose une seule ligne avec le code du mélange; les codes possibles par ingrédient peuvent figurer dans la justification uniquement, pas comme lignes séparées. "
            "4) En cas d'informations contradictoires (ex: étiquette « alcoolisée » mais teneur 0 %), privilégie les critères objectifs (teneur en alcool, composition) et propose une seule ligne recommandée; mentionne les alternatives dans le narrative ou la justification, pas comme lignes à valider. "
            "5) Si la description est vague ou peut correspondre à plusieurs types de produits (ex: « appareil électronique portable avec écran et batterie »), signale-le dans le narrative, baisse la confiance ou demande des précisions, et ne propose qu'une seule hypothèse en indiquant clairement qu'elle est indicative. "
            "6) Ne prétends jamais que la classification est officielle ou définitive. Dans le narrative, rappelle que la proposition doit être validée avant toute utilisation officielle. "
            "7) Si l'entrée décrit un conditionnement/lot (ex: « 2 packs de 12 bouteilles d'eau », « 3 cartons de 10 téléphones »), classe la marchandise contenue (bouteilles d'eau, téléphones), pas le conditionnement. "
            "8) N'ajoute jamais de lignes pour des termes non-marchandise ou méta-informations isolées (ex: « Qte », « Valeur », « Origine », nombres seuls, pays seuls). Si une entrée est non classifiable, n'invente pas de code précis: garde un code non renseigné et une confiance très basse. "
            "9) Pour des variantes proches (singulier/pluriel, accents, alias simples), privilégie l'interprétation métier la plus naturelle et évite de multiplier des lignes quasi identiques inutilement. "
            "10) Si la demande porte sur Mosam (identité, aide, rôle, fonctionnement, règles d'utilisation, origine du projet, etc.) et non sur une marchandise, réponds brièvement dans narrative et mets classifications exactement à []. N'invente pas de lignes produit à partir du contexte documentaire. Si tu ne connais pas un fait (ex. auteur du logiciel), dis-le clairement. "
            "11) Un bloc « Complement internet » peut être fourni : utilise-le seulement pour mieux identifier le produit ou des usages courants, jamais pour imposer un code SH ou un taux si le TEC local ne le confirme pas. En cas de conflit, le contexte TEC local et les notes de chapitre priment toujours. "
            "11bis) Une « Description enrichie pour classification » peut résulter d'un agent d'identification préalable : utilise ces éléments (nature, usage, matériaux) pour le raisonnement RGI, mais le code SH doit toujours reposer sur le contexte TEC local ci-dessous, jamais sur la seule connaissance générale ou internet. "
            "12) Sous-position (RGI 6) : ne jamais inventer un code a 8 ou 10 chiffres. Les criteres de subdivision sont lus dans les libelles TEC de la position retenue ; "
            "n'arreter au dernier niveau justifiable ; si une information juridiquement indispensable manque, le signaler et limiter la confiance. "
            "Ton hs_code est une HYPOTHESE : Mosam applique ensuite la discrimination TEC complete avant de confirmer ou tronquer le code. "
            "13) Positions TEC candidates : si un bloc « POSITIONS TEC CANDIDATES (VERROUILLAGE OBLIGATOIRE) » est present, "
            "applique la METHODE D'ANALYSE PAR ELIMINATION en raisonnement interne, puis choisis hs_code "
            "UNIQUEMENT parmi les positions compatibles. Dans la sortie, resume seulement la position retenue "
            "et la principale alternative ecartee; ne recopie pas toute la liste des candidats. "
            "Tu es meilleur pour eliminer que pour deviner. "
            "Tout code hors liste sera conserve seulement comme hypothese provisoire a faible confiance. "
            "Si un bloc « Avertissement discrimination TEC » est present, respecte-le strictement. "
            "Abréviations: D.D. = droits de douane, R.S. = régime statistique, U.S. = unité de mesure. "
            f"{_CLASSIFICATION_OUTPUT_CONTRACT} "
            "Les champs dd_rate, rs_rate et us_unit sont complétés automatiquement par le système depuis le TEC : "
            "mets \"N/R\" si tu n'es pas certain. Pour other_taxes, mets toujours \"N/R\" (TVA hors TEC). "
            "Le champ \"section\" doit être le numéro romain de la section SH correspondant au chapitre retenu. "
            "\"chapter\" contient les deux premiers chiffres du hs_code. Utilise \"Non renseigné\" si une donnée manque. "
            "confidence entre 0 et 100. Une seule ligne par produit demandé; pas de lignes pour composants, emballage primaire ou « poids ». "
            "Le champ \"justification\" est obligatoire pour chaque classification : il doit indiquer explicitement la ou les RGI appliquées "
            "(ex. « RGI 1 », « RGI 3 b », « RGI 6 ») en tête de phrase, puis un résumé structuré "
            "(fonction principale, nature technique, motif du code retenu et principale alternative écartée). "
            "Reste sous 450 caractères; le moteur local ajoute la trace TEC et les alternatives détaillées. "
            "Ne pas créer de champ séparé pour la RGI : tout le raisonnement juridique va dans \"justification\". "
            "Utilise \"classification_status\" = \"confirmee\" si les informations indispensables sont présentes, sinon \"provisoire\". "
            "14) PRINCIPE DE CLASSIFICATION PAR NATURE TECHNIQUE (essentiel pour les equipements industriels) : "
            "classe le produit selon ce qu'il EST techniquement (sa nature physique), pas selon ce a quoi il SERT (son application). "
            "Exemple : un variateur de frequence CONVERTIT l'energie electrique (change la frequence/tension) → c'est un convertisseur statique, "
            "meme si son APPLICATION est de controler la vitesse d'un moteur. "
            "Un automate programmable (PLC/API) est un appareil de COMMANDE industrielle (il commande/pilote des processus via des entrees/sorties), "
            "pas une machine de traitement de donnees a usage general. "
            "Lis attentivement l'intitule COMPLET et les sous-positions de chaque position candidate. "
            "Choisis la position dont le libelle decrit le plus precisement la NATURE TECHNIQUE du produit. "
            "Quand plusieurs positions semblent possibles, prefere celle qui est la plus specifique au produit plutot qu'une position generique. "
            "REGLE ABSOLUE : ne retourne JAMAIS classifications = []. Si tu ne peux pas determiner un code precis, "
            "retourne au minimum le chapitre le plus probable (XX.XX), confidence <= 40, classification_status = provisoire."
        )

        model = _select_classification_model(prompt_text)
        logger.info(
            "[use_llm] classification model selected=%s routing=%s cheap_configured=%s prompt_len=%s",
            model,
            _classification_model_routing_policy(),
            bool((getattr(Config, "MOSAM_CLASSIFICATION_MODEL_CHEAP", "") or "").strip()),
            len(prompt_text or ""),
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt_text},
            ],
            response_format={"type": "json_object"},
            **chat_completion_kwargs(
                model,
                max_tokens=_classification_max_tokens(prompt_text),
                temperature=0.2,
            ),
        )
        usage = getattr(response, "usage", None)
        record_telemetry_call(
            "classification_llm",
            model=model,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            prompt_chars=len(prompt_text or ""),
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            success=True,
        )

        content = response.choices[0].message.content
        finish = response.choices[0].finish_reason
        if finish == "length":
            logger.warning("[use_llm] response truncated (finish_reason=length)")
            content = _repair_truncated_json(content or "")
        return content

    except Exception as e:
        record_telemetry_call(
            "classification_llm",
            model=model or None,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            prompt_chars=len(prompt_text or ""),
            success=False,
        )
        return f"Erreur lors de l'appel au modèle OpenAI : {e}"


# Libellés fréquents quand l’utilisateur colle tout le bloc de l’UI (évite N requêtes / N classifications fantômes).
_UI_BOILERPLATE_SUBSTRINGS: tuple[str, ...] = (
    "decrire la marchandise",
    "decrivez la marchandise",
    "decrivez la marchandise a classer",
    "matiere, usage, caracteristiques",
    "une ou plusieurs lignes ou puces",
    "une ligne ou une puce par article",
    "ou envoyer un fichier",
    "fichier (txt, pdf)",
    "fichier txt, pdf",
    "lancer la classification",
    "resultat structure",
    "proposition indicative, a faire valider",
    "proposition indicative",
    "dossier entreprise (optionnel)",
    "dossier entreprise",
    "ex: Mosam Entreprise",
    "tout valider",
    "classification(s) recue(s)",
    "unite(s) classee(s)",
    "quantite cumulee",
    "detail calcul quantite",
    "qte retenue:",
    "source: valeur explicite",
    "confiance extraction",
    "section / chapitre",
    "reessayer",
    "aucune classification detectee",
    "reponse recue, mais",
    "origine : non renseigne",
    "valeur : non renseigne",
    "origine: non renseigne",
    "valeur: non renseigne",
    "analyse indicative des marchandises",
)
_UI_BOILERPLATE_TABLE_ROW_HINT = re.compile(
    r"(?is)\bmarchandise\b.*\bqte\b.*\b(?:code|tec)",
)


def is_ui_boilerplate_line(text: str) -> bool:
    """True si la ligne ressemble à de l’aide / en-tête UI, pas à une désignation de marchandise."""
    t = (text or "").strip()
    if not t:
        return True
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return True
    if _UI_BOILERPLATE_TABLE_ROW_HINT.search(t):
        return True
    return any(s in t for s in _UI_BOILERPLATE_SUBSTRINGS)


def split_user_queries(raw_text):
    """Découpe l'entrée utilisateur si plusieurs articles sont fournis d'un coup."""
    if not raw_text:
        return []
    normalized = raw_text.replace("\r", "\n").strip()
    if _is_single_structured_dossier(normalized):
        return [_strip_leading_list_marker(normalized)]

    if "\n\n" in normalized:
        blocks = [b.strip() for b in normalized.split("\n\n") if b.strip()]
        if len(blocks) > 1 and all(_is_single_structured_dossier(b) for b in blocks):
            return [_strip_leading_list_marker(b) for b in blocks]

    raw_lines = normalized.split("\n")
    list_line_re = re.compile(r"^\s*(?:[-*•]|\d+[\.\)])\s+")

    kept: list[tuple[str, str]] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        content = re.sub(r"^[\-\*\d\)\.]+\s*", "", stripped).strip()
        if not content:
            continue
        if is_ui_boilerplate_line(content):
            continue
        kept.append((stripped, content))

    if not kept:
        one = _meta_collapse_ws(normalized)
        return [one] if one else []

    if len(kept) == 1:
        queries = [kept[0][1]]
    else:
        list_marked = sum(1 for s, _ in kept if list_line_re.match(s))
        if list_marked >= 2:
            queries = [c for _, c in kept]
        else:
            queries = [" ".join(c for _, c in kept)]

    if len(queries) > 1:
        return queries
    one = queries[0] if queries else ""
    if ";" in one:
        semi_parts = [seg.strip() for seg in one.split(";") if seg.strip()]
        if len(semi_parts) > 1:
            return semi_parts
    return [one.strip()] if one.strip() else []


def _strip_leading_list_marker(text: str) -> str:
    """Retire un tiret / puce en tête (saisie tableau convertie en liste)."""
    return re.sub(r"^\s*[-*•]\s+", "", (text or "").strip(), count=1)


def _is_single_structured_dossier(text: str) -> bool:
    """Une fiche Produit + sections (composition, quantite, origine, etc.) = une seule marchandise."""
    normalized = _strip_leading_list_marker((text or "").replace("\r", "\n").strip())
    if not normalized:
        return False
    product_headers = re.findall(
        r"(?im)^(?:produit|marchandise|article|designation)\s*:\s*.+",
        normalized,
    )
    if len(product_headers) != 1:
        return False
    return bool(
        re.search(
            r"(?im)^(?:composition|caracteristique|specification|usage|capacite|"
            r"quantite|origine|valeur|devise)\s*:",
            normalized,
        )
    )


def build_context_for_query(query, chunks, index):
    """Génère un contexte documentaire pour une requête précise (legacy / tests)."""
    locked_context, _ = retrieve_locked_tec_context(
        query,
        chunks,
        index,
        search_fn=search_faiss_index,
    )
    return locked_context


def _build_customs_search_terms(
    product_type: str,
    function_usage: str,
    family: str = "",
) -> str:
    """Build a FAISS query from industrial vocabulary mapped to TEC terms."""
    return " ".join(_build_customs_label_keywords(product_type, function_usage, family))


def _build_customs_label_keywords(
    product_type: str,
    function_usage: str,
    family: str = "",
) -> list[str]:
    """Map industrial product vocabulary to TEC heading keywords."""
    combined = f"{product_type} {function_usage} {family}".lower()
    keywords: set[str] = set()

    if any(w in combined for w in ["automate", "programmable", "plc", "api", "simatic", "controleur", "contrôleur"]):
        keywords.update(["commande", "tableau", "panneau", "console", "armoire"])
    if any(w in combined for w in ["industrial control", "control equipment", "controller"]):
        keywords.update(["commande", "tableau", "panneau", "console", "armoire"])
    if any(
        w in combined
        for w in [
            "variateur", "onduleur", "redresseur", "inverter", "vfd", "convertisseur",
            "power converter", "variable speed drive", "motor drive", "frequency drive",
        ]
    ):
        keywords.update(["convertisseur", "statique", "redresseur", "commande", "moteur"])
    if any(w in combined for w in ["connecteur", "connector", "fiche", "douille", "jack"]):
        keywords.update(["connecteur", "fiche", "douille"])
    if any(w in combined for w in ["transceiver", "sfp", "gbic", "optique", "fibre"]):
        keywords.update(["transmission", "reception", "convertisseur", "signaux", "telecommunication"])
    if any(w in combined for w in ["disjoncteur", "breaker", "fusible", "sectionneur"]):
        keywords.update(["disjoncteur", "fusible", "coupure", "sectionnement"])
    if any(w in combined for w in ["switch", "commut", "routeur", "router", "ethernet"]):
        keywords.update(["commutation", "transmission", "reception", "telecommunication"])
    if any(phrase in combined for phrase in [
        "data storage system", "storage unit", "baie de stockage",
        "storage array", "unite de stockage",
    ]):
        keywords.update(["unites", "memoire", "traitement", "information", "stockage", "machines", "automatiques"])
    if any(phrase in combined for phrase in [
        "accelerator", "expansion card", "carte acceleratrice", "gpu pcie",
    ]):
        keywords.update(["parties", "accessoires", "machines", "traitement", "information", "cartes", "modules"])
    if any(phrase in combined for phrase in [
        "server automatic data processing", "serveur informatique", "serveur rack",
    ]):
        keywords.update(["machines", "automatiques", "traitement", "information", "unites", "serveur"])
    if any(phrase in combined for phrase in [
        "rugged mobile data", "terminal mobile", "terminal durci", "data collection terminal",
    ]):
        keywords.update(["portatives", "traitement", "information", "entree", "sortie", "unites"])
    if any(phrase in combined for phrase in [
        "industrial robot", "robot industriel", "operations robotisees", "bras robotise",
    ]):
        keywords.update(["robots", "industriels", "machines", "fonction", "propre"])
    is_tablet = any(w in combined for w in ["tablet", "tablette"])
    if is_tablet:
        keywords.update(["traitement", "information", "portatives", "ordinateur", "machines", "automatiques", "unites"])
    elif any(w in combined for w in ["smartphone", "telephone", "cellulaire"]):
        keywords.update(["telephone", "intelligent", "cellulaire"])
    if any(
        w in combined
        for w in [
            "digital camera", "camera numerique", "camera video", "ip camera",
            "network camera", "thermal camera", "camera thermique", "multispectral",
            "surveillance camera", "camera de surveillance", "imaging camera",
            "thermal imaging camera", "video or thermal imaging",
        ]
    ):
        keywords.update(["cameras", "photographiques", "numeriques", "camescopes", "television", "video"])
    if any(
        w in combined
        for w in [
            "mixed reality", "realite mixte", "virtual reality", "realite virtuelle",
            "immersive headset", "display headset", "wearable display",
        ]
    ):
        keywords.update(["moniteurs", "projecteurs", "affichage", "video", "ecrans", "casques"])
    if any(w in combined for w in ["excavat", "pelle", "bulldozer", "chargeuse", "engin", "terrassement"]):
        keywords.update(["excavateur", "pelle", "chenille", "terrassement"])
    if any(w in combined for w in ["capteur", "sensor", "sonde", "transducteur"]):
        keywords.update(["transducteur", "capteur", "instrument", "mesure"])
    if any(w in combined for w in ["cable", "fil", "conducteur", "rj45"]):
        keywords.update(["fil", "cable", "conducteur", "cuivre"])
    if any(
        phrase in combined
        for phrase in [
            "vacuum flask", "vacuum bottle", "insulated flask", "insulated bottle",
            "thermos", "recipient isotherme", "récipient isotherme", "bouteille isolante",
        ]
    ):
        keywords.update(["bouteilles isolantes", "recipients isothermiques", "sous vide"])
    if (
        re.search(r"\bled\b", combined)
        or any(
            phrase in combined
            for phrase in [
                "light bulb", "ampoule", "diode lamp", "household bulb",
                "lampe a diode", "lampe à diode",
            ]
        )
    ):
        keywords.update(["lampes", "diodes", "emettrices", "lumiere"])
    if any(
        phrase in combined
        for phrase in [
            "woven sack", "woven bag", "packing sack", "packaging sack",
            "polypropylene sack", "polypropylene bag", "sac tisse", "sac tissé",
        ]
    ):
        keywords.update(["sacs", "sachets", "emballage"])

    if any(
        phrase in combined
        for phrase in [
            "syringe", "seringue", "medical syringe", "disposable syringe",
            "hypodermic", "injector", "injection", "aiguille", "needle",
        ]
    ):
        keywords.update(["seringues", "aiguilles", "catheters", "instruments", "medicaux"])

    return sorted(keywords)


def _build_tec_discrimination_hint(
    source_text: str,
    candidate_dicts: list[dict[str, Any]] | None = None,
) -> str:
    """
    Signale au LLM les critères discriminants TEC non vérifiables pour les positions candidates.
    """
    from .tariff_subposition import (
        position_has_discriminating_subpositions,
        preview_missing_discriminating_criteria,
    )

    positions: list[str] = []
    if candidate_dicts:
        for entry in candidate_dicts:
            pos = str(entry.get("position_code") or "").strip()
            if pos and pos not in positions:
                positions.append(pos)
    if not positions:
        return ""

    lines = [
        "Avertissement discrimination TEC (hypothèse seulement — le moteur Mosam tranchera après) :"
    ]
    any_hint = False
    for position in positions[:3]:
        if not position_has_discriminating_subpositions(position):
            continue
        missing = preview_missing_discriminating_criteria(position, source_text)
        if not missing:
            continue
        any_hint = True
        preview = "; ".join(missing[:3])
        lines.append(
            f"- Position {position} : critères discriminants manquants ou non vérifiables ({preview}). "
            "Si tu retiens cette position, limite hs_code au niveau 4 chiffres."
        )
    if not any_hint:
        return ""
    return "\n" + "\n".join(lines) + "\n"


@dataclass
class ClassificationPipelineResult:
    """Reponse LLM + identification produit par marchandise."""

    llm_raw: str
    product_identifications: list[dict[str, Any]] = field(default_factory=list)


def process_user_input(
    user_input,
    chunks,
    index,
    validated_index: faiss.Index | None = None,
    validated_meta: list[dict[str, object]] | None = None,
    progress: ClassificationProgressReporter | None = None,
    *,
    skip_identification: bool = False,
) -> ClassificationPipelineResult:
    if is_assistant_meta_query(user_input):
        logger.debug("meta query about assistant; skip RAG/LLM classification")
        return ClassificationPipelineResult(
            llm_raw=build_assistant_meta_response_json(user_input)
        )

    queries = split_user_queries(user_input)
    if not queries:
        return ClassificationPipelineResult(
            llm_raw="Merci de préciser au moins une marchandise à classifier."
        )

    if progress:
        if skip_identification:
            progress.skip("identification")
        else:
            progress.start("identification")

    prepared: list[tuple[str, str, Any]] = []
    product_identifications: list[dict[str, Any]] = []
    identification_skipped = skip_identification
    for query in queries:
        if skip_identification:
            text = (query or "").strip()
            product_ref = text
            if text.lower().startswith("produit :"):
                product_ref = text.split(":", 1)[1].strip().split("\n", 1)[0].strip()
            identification = ProductIdentification(
                original_query=text,
                enriched_description=text,
                product_name=product_ref[:120] or text[:120],
                identification_confidence=100,
                skipped=True,
                skip_reason="structured_form",
            )
            classification_query = text
        else:
            classification_query, identification = prepare_query_for_classification(query)
            if not identification.skipped:
                identification_skipped = False
        product_identifications.append(identification.to_dict())
        prepared.append((query, classification_query, identification))

    if progress:
        if not skip_identification:
            if identification_skipped:
                progress.skip("identification")
            else:
                progress.complete("identification")
        progress.start("tec_context")

    prompt_sections = []
    for i, (query, classification_query, identification) in enumerate(prepared, start=1):
        unstable = getattr(identification, "identification_unstable", False)
        primary_query = query.strip() if unstable else classification_query
        identification_dict = identification.to_dict()
        functional_profile = build_functional_profile(
            classification_query,
            identification_dict,
        )
        product_evidence = build_product_evidence(
            query,
            identification_dict,
            functional_profile,
        )
        increment_telemetry("functional_profiles_built")
        increment_telemetry("product_evidence_records_built")
        if i - 1 < len(product_identifications):
            product_identifications[i - 1]["functional_profile"] = functional_profile.to_dict()
            product_identifications[i - 1]["product_evidence"] = product_evidence.to_dict()

        retrieval_primary_query = primary_query
        evidence_query = product_evidence.retrieval_query()
        evidence_driven_primary = bool(
            identification.skipped
            and product_evidence.technical_nature_confidence >= 70
            and evidence_query
        )
        if evidence_driven_primary:
            retrieval_primary_query = evidence_query
            increment_telemetry("evidence_driven_primary_retrievals")

        locked_context, candidate_dicts = retrieve_locked_tec_context(
            retrieval_primary_query,
            chunks,
            index,
            search_fn=search_faiss_index,
        )

        structured_query = product_evidence.retrieval_query() or classification_query
        structured_candidates = search_structured_tariff_positions(
            structured_query,
            top_n=6,
        )
        if structured_candidates:
            candidate_dicts.extend(structured_candidates)
            increment_telemetry("structured_lexical_retrievals")

        # Detailed structured rows skip paid product identification. Preserve
        # that cost saving while still applying local customs vocabulary and
        # direct TEC heading matching to the complete source description.
        if identification.skipped and bool(
            getattr(Config, "MOSAM_RAG_HEADING_MATCH_ENABLED", True)
        ):
            structured_keywords = _build_customs_label_keywords(
                functional_profile.product_type,
                functional_profile.primary_function,
                functional_profile.family,
            )
            if structured_keywords:
                min_matches = 2 if len(structured_keywords) >= 3 else 1
                direct_matches = find_positions_by_label_keywords(
                    structured_keywords,
                    min_matches=min_matches,
                    top_n=4,
                )
                promoted: list[dict[str, Any]] = []
                promoted_positions: set[str] = set()
                for pos_code, heading_label, score in direct_matches:
                    promoted.append({
                        "position_code": pos_code,
                        "label": heading_label,
                        "score": 10.0 + float(score),
                        "chapter": pos_code.replace(".", "")[:2],
                        "excerpt": "",
                        "matched_codes": [],
                        "affinity_note": "Correspondance directe avec le type de produit structure",
                        "candidate_sources": ["direct_label_keywords"],
                    })
                    promoted_positions.add(pos_code)
                candidate_dicts = promoted + [
                    entry
                    for entry in candidate_dicts
                    if entry.get("position_code") not in promoted_positions
                ]

            existing_positions = {d.get("position_code") for d in candidate_dicts}
            functional_query = functional_profile.functional_query()
            extra_searches_enabled = bool(
                getattr(Config, "MOSAM_RAG_EXTRA_SEARCHES_ENABLED", True)
            )
            if (
                extra_searches_enabled
                and not evidence_driven_primary
                and functional_query
                and functional_query.casefold() != retrieval_primary_query.casefold()
            ):
                increment_telemetry("functional_profile_retrievals")
                _, functional_candidates = retrieve_locked_tec_context(
                    functional_query,
                    chunks,
                    index,
                    search_fn=search_faiss_index,
                )
                for candidate in functional_candidates:
                    position = candidate.get("position_code")
                    if position not in existing_positions:
                        candidate_dicts.append(candidate)
                        existing_positions.add(position)

            direct_function_matches = find_positions_by_heading_match(
                classification_query,
                product_type=functional_profile.product_type,
                function_usage=functional_profile.primary_function,
                family=functional_profile.family,
            )
            for pos_code, heading_label, score in direct_function_matches:
                if pos_code not in existing_positions:
                    candidate_dicts.append({
                        "position_code": pos_code,
                        "label": heading_label,
                        "score": 5.0 + float(score),
                        "chapter": pos_code.replace(".", "")[:2],
                        "excerpt": "",
                        "matched_codes": [],
                        "affinity_note": "Correspondance avec le profil fonctionnel structure",
                        "candidate_sources": ["functional_heading_match"],
                    })
                    existing_positions.add(pos_code)

            for hint_phrase in _build_heading_hint_phrases(
                functional_profile.product_type,
                functional_profile.primary_function,
                functional_profile.family,
            ):
                hinted_matches = find_positions_by_heading_match(
                    hint_phrase,
                    product_type=functional_profile.product_type,
                    function_usage=functional_profile.primary_function,
                    family=functional_profile.family,
                    top_n=2,
                    min_score=0.2,
                )
                for pos_code, heading_label, score in hinted_matches:
                    if pos_code not in existing_positions:
                        candidate_dicts.append({
                            "position_code": pos_code,
                            "label": heading_label,
                            "score": 6.0 + float(score),
                            "chapter": pos_code.replace(".", "")[:2],
                            "excerpt": "",
                            "matched_codes": [],
                            "affinity_note": "Correspondance avec un libelle generique de famille technique",
                            "candidate_sources": ["generic_heading_hint"],
                        })
                        existing_positions.add(pos_code)

            if candidate_dicts:
                candidate_dicts = rerank_candidates_by_affinity(
                    candidate_dicts,
                    product_type=functional_profile.product_type,
                    function_usage=functional_profile.primary_function,
                    family=functional_profile.family,
                )
                candidate_dicts = limit_position_candidates(candidate_dicts)
                locked_context = format_merged_candidates_prompt(candidate_dicts)

        if unstable and primary_query.casefold() != classification_query.casefold():
            _, enriched_candidates = retrieve_locked_tec_context(
                classification_query, chunks, index, search_fn=search_faiss_index,
            )
            existing = {d.get("position_code") for d in candidate_dicts}
            for fc in enriched_candidates:
                if fc.get("position_code") not in existing:
                    candidate_dicts.append(fc)
                    existing.add(fc.get("position_code"))

        if not identification.skipped:
            existing_positions = {d.get("position_code") for d in candidate_dicts}
            extra_searches_enabled = bool(getattr(Config, "MOSAM_RAG_EXTRA_SEARCHES_ENABLED", True))
            heading_match_enabled = bool(getattr(Config, "MOSAM_RAG_HEADING_MATCH_ENABLED", True))

            # 2nd FAISS query: product_type + function_usage
            func_query = " ".join(filter(None, [
                (identification.product_type or "").strip(),
                (identification.function_usage or "").strip(),
            ]))
            if extra_searches_enabled and func_query and func_query.casefold() != classification_query.casefold():
                _, func_candidates = retrieve_locked_tec_context(
                    func_query, chunks, index, search_fn=search_faiss_index,
                )
                for fc in func_candidates:
                    if fc.get("position_code") not in existing_positions:
                        candidate_dicts.append(fc)
                        existing_positions.add(fc.get("position_code"))

            # 3rd FAISS query: family (product family/category)
            family = getattr(identification, "family", "") or ""
            family = family.strip()
            if extra_searches_enabled and family and family.casefold() != func_query.casefold() and family.casefold() != classification_query.casefold():
                _, family_candidates = retrieve_locked_tec_context(
                    family, chunks, index, search_fn=search_faiss_index,
                )
                for fc in family_candidates:
                    if fc.get("position_code") not in existing_positions:
                        candidate_dicts.append(fc)
                        existing_positions.add(fc.get("position_code"))

            # 4th source: text matching against position headings
            ptype = (identification.product_type or "").strip()
            fusage = (identification.function_usage or "").strip()
            if heading_match_enabled:
                heading_matches = find_positions_by_heading_match(
                    classification_query,
                    product_type=ptype,
                    function_usage=fusage,
                    family=family,
                )
                for pos_code, heading_label, _score in heading_matches:
                    if pos_code not in existing_positions:
                        candidate_dicts.append({
                            "position_code": pos_code,
                            "label": heading_label,
                            "score": 0.0,
                            "chapter": pos_code.replace(".", "")[:2],
                            "excerpt": "",
                            "matched_codes": [],
                            "candidate_sources": ["identified_heading_match"],
                        })
                        existing_positions.add(pos_code)

            # 5th source: FAISS with customs-oriented vocabulary
            customs_terms = _build_customs_search_terms(ptype, fusage, family)
            if extra_searches_enabled and customs_terms and customs_terms.casefold() not in {
                classification_query.casefold(),
                func_query.casefold(),
                family.casefold() if family else "",
                primary_query.casefold(),
            }:
                _, customs_candidates = retrieve_locked_tec_context(
                    customs_terms, chunks, index, search_fn=search_faiss_index,
                )
                for fc in customs_candidates:
                    if fc.get("position_code") not in existing_positions:
                        candidate_dicts.append(fc)
                        existing_positions.add(fc.get("position_code"))

            # 6th source: direct match against TEC position headings via customs keywords
            label_keywords = _build_customs_label_keywords(ptype, fusage, family)
            if heading_match_enabled and label_keywords:
                min_matches = 2 if len(label_keywords) >= 3 else 1
                keyword_matches = find_positions_by_label_keywords(
                    label_keywords,
                    min_matches=min_matches,
                    top_n=4,
                )
                for pos_code, heading_label, _score in keyword_matches:
                    if pos_code not in existing_positions:
                        candidate_dicts.append({
                            "position_code": pos_code,
                            "label": heading_label,
                            "score": 0.0,
                            "chapter": pos_code.replace(".", "")[:2],
                            "excerpt": "",
                            "matched_codes": [],
                            "candidate_sources": ["identified_label_keywords"],
                        })
                        existing_positions.add(pos_code)

            if candidate_dicts:
                candidate_dicts = rerank_candidates_by_affinity(
                    candidate_dicts,
                    product_type=ptype,
                    function_usage=fusage,
                    family=family,
                )
                candidate_dicts = limit_position_candidates(candidate_dicts)
                locked_context = format_merged_candidates_prompt(candidate_dicts)

        candidate_dicts = limit_position_candidates(candidate_dicts)
        candidate_summary = summarize_candidate_evidence(candidate_dicts)
        increment_telemetry("candidate_sets_built")
        increment_telemetry("candidate_positions_total", candidate_summary["candidate_count"])
        increment_telemetry("candidate_chapters_total", candidate_summary["chapter_count"])
        if candidate_summary["candidate_count"] == 0:
            increment_telemetry("candidate_sets_empty")
        elif candidate_summary["chapter_count"] <= 1:
            increment_telemetry("candidate_sets_single_chapter")
        if candidate_summary["max_affinity"] < 0.12:
            increment_telemetry("candidate_sets_low_affinity")
        logger.info(
            "[candidate-recall] item=%s positions=%s chapters=%s max_affinity=%.3f sources=%s",
            i,
            candidate_summary["positions"],
            candidate_summary["chapters"],
            candidate_summary["max_affinity"],
            candidate_summary["sources"],
        )
        locked_context = format_merged_candidates_prompt(candidate_dicts)
        if i - 1 < len(product_identifications):
            product_identifications[i - 1]["tec_position_candidates"] = candidate_dicts
            product_identifications[i - 1]["candidate_retrieval"] = candidate_summary

        # Rich structured rows already have an official TEC candidate set. Re-embedding
        # the row only to retrieve historical examples adds cost and can re-introduce
        # stale human decisions into an otherwise official-document-driven decision.
        # Keep examples as a fallback when official retrieval found no candidates.
        if identification.skipped and candidate_dicts:
            examples_context = ""
            increment_telemetry("structured_validated_examples_skipped")
        else:
            examples_context = build_validated_examples_context(
                classification_query,
                validated_index,
                validated_meta,
            )
        examples_block = f"\n{examples_context}" if examples_context else ""

        original_note = ""
        if identification.enriched_description.strip() and identification.enriched_description.strip() != query.strip():
            original_note = f"\nSaisie utilisateur initiale : {query.strip()}"

        id_function_block = ""
        if not identification.skipped:
            ptype = (identification.product_type or "").strip()
            fusage = (identification.function_usage or "").strip()
            manufacturer = (identification.manufacturer or "").strip()
            commercial = (identification.commercial_name or "").strip()
            mpn = (identification.manufacturer_part_number or "").strip()
            family = getattr(identification, "family", "") or ""
            family = family.strip()
            why_not = getattr(identification, "why_not_other_products", "") or ""
            why_not = why_not.strip()
            reasoning = getattr(identification, "reasoning", "") or ""
            reasoning = reasoning.strip()
            if ptype or fusage or unstable:
                ref_confirmed = _identification_matches_reference(query, identification)
                product_ref = (
                    mpn
                    or commercial
                    or query.strip()
                )
                lines = ["PRODUIT IDENTIFIE :"]
                if product_ref:
                    lines.append(product_ref)
                lines.append("")
                if manufacturer:
                    lines.append(f"Fabricant : {manufacturer}")
                if ptype and (not unstable or ref_confirmed):
                    lines.append(f"Type : {ptype}")
                if fusage and (not unstable or ref_confirmed):
                    lines.append(f"Fonction : {fusage}")
                if family and (not unstable or ref_confirmed):
                    lines.append(f"Famille : {family}")
                if unstable:
                    lines.append("")
                    lines.append(
                        "ATTENTION : identification incertaine ou non confirmee. "
                        f"Reference utilisateur prioritaire : {query.strip()}. "
                        "Ne te fie pas a une hypothese produit erronnee ; "
                        "confidence <= 55, classification_status = provisoire."
                    )
                if reasoning and (not unstable or ref_confirmed):
                    lines.append(f"Raisonnement identification : {reasoning}")
                if why_not and (not unstable or ref_confirmed):
                    lines.append(f"Produits ecartes : {why_not}")
                lines.append("")
                lines.append(
                    "Analyse CHAQUE position TEC candidate (compatible / incompatible / incertain + pourquoi), "
                    "puis choisis uniquement parmi les positions compatibles."
                )
                id_function_block = "\n" + "\n".join(lines) + "\n"

        product_evidence_block = "\n" + product_evidence.prompt_block() + "\n"

        web_block = ""
        if getattr(identification, "web_search_used", False):
            source_lines = [
                "Complement internet (sources consultees — ne pas imposer de code SH ni de taux) :"
            ]
            for source in getattr(identification, "web_sources", None) or []:
                title = str(source.get("title") or source.get("url") or "").strip()
                url = str(source.get("url") or "").strip()
                if url:
                    source_lines.append(f"- {title}: {url}")
            for query_term in getattr(identification, "web_search_queries", None) or []:
                q = str(query_term).strip()
                if q:
                    source_lines.append(f"- Recherche effectuee : {q}")
            if len(source_lines) > 1:
                web_block = "\n" + "\n".join(source_lines) + "\n"

        tec_hint = _build_tec_discrimination_hint(classification_query, candidate_dicts)

        prompt_sections.append(
            f"[MARCHANDISE {i}]\nDescription enrichie pour classification :\n{classification_query}"
            f"{original_note}{id_function_block}{product_evidence_block}"
            f"{web_block}{tec_hint}\n{locked_context}{examples_block}"
        )

    combined_context = "\n\n".join(prompt_sections)
    enriched_prompt = (
        "L'utilisateur peut avoir fourni plusieurs marchandises. "
        "Pour chaque bloc ci-dessous : analyse chaque position TEC candidate "
        "(compatible / incompatible / incertain + pourquoi), elimine les positions incompatibles, "
        "puis retiens hs_code uniquement parmi les positions compatibles. "
        "Tu es meilleur pour eliminer que pour deviner. "
        "La discrimination TEC des sous-positions est appliquee ensuite par Mosam.\n\n"
        f"{combined_context}\n\nDemande initiale de l'utilisateur:\n{user_input}"
    )
    logger.debug("start the send of the question")
    if progress:
        progress.complete("tec_context")
        progress.start("position_hypothesis")
    response = use_llm(enriched_prompt)
    logger.debug("finish the send of the question")

    if progress:
        progress.complete("position_hypothesis")

    return ClassificationPipelineResult(
        llm_raw=response,
        product_identifications=product_identifications,
    )
