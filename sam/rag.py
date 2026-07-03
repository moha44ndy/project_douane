import glob
import faiss
import numpy as np
import pathlib
import requests
import os
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any
from .config.settings import Config
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
from .product_identification import prepare_query_for_classification
from .candidate_set_enforcer import (
    attach_candidates_to_classifications,
    retrieve_locked_tec_context,
)
from .classification_progress import ClassificationProgressReporter

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


def search_faiss_index(query, index, k=5):
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
def use_llm(prompt_text):
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
            "tu DOIS choisir hs_code uniquement parmi ces positions (XX.XX ou sous-code de l'une d'elles). "
            "Justifie explicitement pourquoi les autres candidates sont ecartees. "
            "Tout code hors liste sera rejete par Mosam. "
            "Si un bloc « Avertissement discrimination TEC » est present, respecte-le strictement. "
            "Abréviations: D.D. = droits de douane, R.S. = régime statistique, U.S. = unité de mesure. "
            "Retourne exclusivement un objet JSON (aucun texte hors JSON) de la forme: "
            "{\"narrative\":\"texte pour l'utilisateur (avec rappel: proposition indicative, à faire valider avant toute utilisation officielle)\",\"classifications\":[{"
            "\"description\":\"Résumé de la marchandise\",\"hs_code\":\"8517.13.00.00\","
            "\"section\":\"XVI\",\"section_name\":\"Machines et appareils; matériel électrique\","
            "\"chapter\":\"85\",\"chapter_name\":\"Machines, appareils et matériel électrique\","
            "\"justification\":\"RGI 1 : [règle appliquée] — fonction principale, caractère essentiel, chapitres envisagés/écartés, motif du code retenu\",\"excerpt\":\"Citation si pertinent\","
            "\"origin\":\"Non renseigné\",\"value\":\"Non renseigné\",\"confidence\":90,"
            "\"classification_status\":\"confirmee\"}]}. "
            "Les champs dd_rate, rs_rate et us_unit sont complétés automatiquement par le système depuis le TEC : "
            "mets \"N/R\" si tu n'es pas certain. Pour other_taxes, mets toujours \"N/R\" (TVA hors TEC). "
            "Le champ \"section\" doit être le numéro romain de la section SH qui contient le chapitre (ex: code 8517 → chapitre 85 → section XVI). "
            "\"chapter\" = les deux premiers chiffres du code (ex: 85). Utilise \"Non renseigné\" si une donnée manque. "
            "confidence entre 0 et 100. Une seule ligne par produit demandé; pas de lignes pour composants, emballage primaire ou « poids ». "
            "Le champ \"justification\" est obligatoire pour chaque classification : il doit indiquer explicitement la ou les RGI appliquées "
            "(ex. « RGI 1 », « RGI 3 b », « RGI 6 ») en tête de phrase, puis le raisonnement structuré "
            "(fonction principale de la marchandise, caractère essentiel, chapitres ou positions étudiés et écartés avec motif, motif du code SH retenu). "
            "Mentionne explicitement les chapitres ou positions écartés (ex. « chapitre 76 écarté car… ») pour alimenter l'analyse des alternatives. "
            "Ne pas créer de champ séparé pour la RGI : tout le raisonnement juridique va dans \"justification\". "
            "Utilise \"classification_status\" = \"confirmee\" si les informations indispensables sont présentes, sinon \"provisoire\"."
        )

        # Utilise l'API de chat du client OpenAI (SDK >= 1.x)
        response = client.chat.completions.create(
            model=Config.MOSAM_MODEL or "gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt_text},
            ],
            max_tokens=2048,
        )

        return response.choices[0].message.content

    except Exception as e:
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
        return [normalized]

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


def _is_single_structured_dossier(text: str) -> bool:
    """Une fiche Produit + sections (composition, quantite, origine, etc.) = une seule marchandise."""
    normalized = (text or "").replace("\r", "\n").strip()
    if not normalized:
        return False
    if not re.search(
        r"(?im)^(?:produit|marchandise|article|designation)\s*:\s*.+",
        normalized,
    ):
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
        progress.start("identification")

    prepared: list[tuple[str, str, Any]] = []
    product_identifications: list[dict[str, Any]] = []
    for query in queries:
        classification_query, identification = prepare_query_for_classification(query)
        product_identifications.append(identification.to_dict())
        prepared.append((query, classification_query, identification))

    if progress:
        progress.complete("identification")
        progress.start("tec_context")

    prompt_sections = []
    for i, (query, classification_query, identification) in enumerate(prepared, start=1):
        locked_context, candidate_dicts = retrieve_locked_tec_context(
            classification_query,
            chunks,
            index,
            search_fn=search_faiss_index,
        )
        if i - 1 < len(product_identifications):
            product_identifications[i - 1]["tec_position_candidates"] = candidate_dicts

        examples_context = build_validated_examples_context(
            classification_query,
            validated_index,
            validated_meta,
        )
        examples_block = f"\n{examples_context}" if examples_context else ""

        original_note = ""
        if identification.enriched_description.strip() and identification.enriched_description.strip() != query.strip():
            original_note = f"\nSaisie utilisateur initiale : {query.strip()}"

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
            f"{original_note}{web_block}{tec_hint}\n{locked_context}{examples_block}"
        )

    combined_context = "\n\n".join(prompt_sections)
    enriched_prompt = (
        "L'utilisateur peut avoir fourni plusieurs marchandises. "
        "Analyse chaque bloc ci-dessous et produis une réponse structurée avec, pour chaque marchandise, "
        "une hypothèse de position tarifaire (pas une classification définitive — la discrimination TEC "
        "des sous-positions est appliquée ensuite par Mosam), le taux d'imposition indicatif et les détails pertinents.\n\n"
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