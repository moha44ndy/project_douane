import glob
import faiss
import numpy as np
import pathlib
import requests
import os
import re
from .config.settings import Config
from .app_logger import get_logger
from dotenv import load_dotenv
import threading
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain_community.document_loaders import PyPDFLoader
from requests.auth import HTTPBasicAuth
from sqlalchemy import text as sql_text

from .db import get_db
import urllib3
import json
from openai import OpenAI

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Nouveau client OpenAI (SDK >= 1.x)
client = OpenAI(api_key=Config.OPENAI_API_KEY)

logger = get_logger(__name__)

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
    with open(meta_path, "w", encoding="utf-8") as f:
        # Convertit les champs non sérialisables (ex: UUID) en string.
        def _jsonify(obj: object) -> object:
            try:
                import uuid as _uuid

                if isinstance(obj, _uuid.UUID):
                    return str(obj)
            except Exception:
                pass
            try:
                import decimal as _decimal

                if isinstance(obj, _decimal.Decimal):
                    # On convertit en string pour eviter les erreurs de precision.
                    return str(obj)
            except Exception:
                pass
            if isinstance(obj, dict):
                return {k: _jsonify(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_jsonify(v) for v in obj]
            return obj

        json.dump(_jsonify(meta), f, ensure_ascii=False, indent=2)


def _load_classifications_index_from_disk() -> tuple[faiss.Index, list[dict[str, object]]]:
    index_path, meta_path = _classifications_index_paths()
    expected_dim = _embedding_dim_probe()
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        empty = faiss.IndexFlatL2(expected_dim)
        return empty, []

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
        return _rebuild_classifications_index_from_db()

    if index.d != expected_dim or int(index.ntotal) != len(meta):
        logger.warning(
            "[validated_classifications] index incompatible, reconstruction requise (index.d=%s expected_dim=%s ntotal=%s meta_len=%s)",
            index.d,
            expected_dim,
            index.ntotal,
            len(meta),
        )
        return _rebuild_classifications_index_from_db()

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
            "Tu es Mosam, un assistant douanier pour la classification tarifaire TEC/SH CEDEAO. "
            "Règles générales d'interprétation (RGI): "
            "RGI 1: Les titres des sections, chapitres et sous-chapitres n'ont qu'une valeur indicative. "
            "RGI 2: Marchandises incomplètes ou non finies classées comme complètes. "
            "RGI 3: Mélange ou assemblage classé selon la matière prépondérante. "
            "RGI 4: Sinon, position la plus analogue. "
            "RGI 5: Les emballages sont classés avec les marchandises qu'ils contiennent (ne pas créer de ligne séparée pour l'emballage primaire: flacon, gobelet doseur, etc.). "
            "RGI 6: Sous-positions selon les termes des sous-positions. "
            "Réponds uniquement aux questions posées. Priorise la clarté et la concision. "
            "Ne mentionne jamais les documents sources; fais comme si les infos étaient internes. "
            "Réponds dans la langue du prompt. "
            "Règles de sortie strictes: "
            "1) Une ligne de classification = un produit distinct demandé par l'utilisateur. Ne décompose jamais un produit en ses composants (écran, processeur, RAM, disque, connecteur, poids, etc.) sauf si l'utilisateur demande explicitement des lignes séparées pour des composants. "
            "2) Si l'utilisateur demande N produits (ex: « Produit 1: ordinateur, Produit 2: chargeur »), retourne au plus N lignes, une par produit. "
            "3) Pour un mélange (ex: mix de fruits secs), propose une seule ligne avec le code du mélange; les codes possibles par ingrédient peuvent figurer dans la justification uniquement, pas comme lignes séparées. "
            "4) En cas d'informations contradictoires (ex: étiquette « alcoolisée » mais teneur 0 %), privilégie les critères objectifs (teneur en alcool, composition) et propose une seule ligne recommandée; mentionne les alternatives dans le narrative ou la justification, pas comme lignes à valider. "
            "5) Si la description est vague ou peut correspondre à plusieurs types de produits (ex: « appareil électronique portable avec écran et batterie »), signale-le dans le narrative, baisse la confiance ou demande des précisions, et ne propose qu'une seule hypothèse en indiquant clairement qu'elle est indicative. "
            "6) Ne prétends jamais que la classification est officielle ou définitive. Dans le narrative, rappelle que la proposition doit être vérifiée par l'autorité douanière. "
            "7) Si l'entrée décrit un conditionnement/lot (ex: « 2 packs de 12 bouteilles d'eau », « 3 cartons de 10 téléphones »), classe la marchandise contenue (bouteilles d'eau, téléphones), pas le conditionnement. "
            "8) N'ajoute jamais de lignes pour des termes non-marchandise ou méta-informations isolées (ex: « Qte », « Valeur », « Origine », nombres seuls, pays seuls). Si une entrée est non classifiable, n'invente pas de code précis: garde un code non renseigné et une confiance très basse. "
            "9) Pour des variantes proches (singulier/pluriel, accents, alias simples), privilégie l'interprétation métier la plus naturelle et évite de multiplier des lignes quasi identiques inutilement. "
            "Abréviations: D.D. = droits de douane, R.S. = régime statistique, U.S. = unité de mesure. "
            "Retourne exclusivement un objet JSON (aucun texte hors JSON) de la forme: "
            "{\"narrative\":\"texte pour le douanier (avec rappel: proposition indicative, à faire valider par l'autorité douanière)\",\"classifications\":[{"
            "\"description\":\"Résumé de la marchandise\",\"hs_code\":\"8517.13.00.00\","
            "\"section\":\"XVI\",\"section_name\":\"Machines et appareils; matériel électrique\","
            "\"chapter\":\"85\",\"chapter_name\":\"Machines, appareils et matériel électrique\","
            "\"dd_rate\":\"5 %\",\"rs_rate\":\"1 %\",\"us_unit\":\"PIÈCE\",\"other_taxes\":\"TVA 18 %\","
            "\"justification\":\"Synthèse RGI / critères\",\"excerpt\":\"Citation si pertinent\","
            "\"origin\":\"Non renseigné\",\"value\":\"Non renseigné\",\"confidence\":90}]}. "
            "Le champ \"section\" doit être le numéro romain de la section SH qui contient le chapitre (ex: code 8517 → chapitre 85 → section XVI). "
            "\"chapter\" = les deux premiers chiffres du code (ex: 85). Utilise \"Non renseigné\" si une donnée manque. "
            "confidence entre 0 et 100. Une seule ligne par produit demandé; pas de lignes pour composants, emballage primaire ou « poids »."
        )

        # Utilise l'API de chat du client OpenAI (SDK >= 1.x)
        response = client.chat.completions.create(
            model=Config.MOSAM_MODEL or "gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt_text},
            ],
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Erreur lors de l'appel au modèle OpenAI : {e}"

def split_user_queries(raw_text):
    """Découpe l'entrée utilisateur si plusieurs articles sont fournis d'un coup."""
    if not raw_text:
        return []
    normalized = raw_text.replace("\r", "\n")
    line_parts = [
        re.sub(r"^[\-\*\d\)\.]+\s*", "", line).strip()
        for line in normalized.split("\n")
    ]
    queries = [part for part in line_parts if part]
    if len(queries) > 1:
        return queries
    if ";" in raw_text:
        semi_parts = [seg.strip() for seg in raw_text.split(";") if seg.strip()]
        if len(semi_parts) > 1:
            return semi_parts
    return [raw_text.strip()] if raw_text.strip() else []


def build_context_for_query(query, chunks, index):
    """Génère un contexte documentaire pour une requête précise."""
    indices, _ = search_faiss_index(query, index)
    context = ""
    for idx in indices[0]:
        context += chunks[idx].page_content + "\n"
    return context


def process_user_input(
    user_input,
    chunks,
    index,
    validated_index: faiss.Index | None = None,
    validated_meta: list[dict[str, object]] | None = None,
):
    queries = split_user_queries(user_input)
    if not queries:
        return "Merci de préciser au moins une marchandise à classifier."

    prompt_sections = []
    for i, query in enumerate(queries, start=1):
        context = build_context_for_query(query, chunks, index)
        examples_context = build_validated_examples_context(query, validated_index, validated_meta)
        examples_block = f"\n{examples_context}" if examples_context else ""
        prompt_sections.append(
            f"[MARCHANDISE {i}]\nDescription: {query}\nContexte documentaire:\n{context}{examples_block}"
        )

    combined_context = "\n\n".join(prompt_sections)
    enriched_prompt = (
        "Le douanier peut avoir fourni plusieurs marchandises. "
        "Analyse chaque bloc ci-dessous et produis une réponse structurée avec, pour chaque marchandise, "
        "la position tarifaire, le taux d'imposition et les détails pertinents.\n\n"
        f"{combined_context}\n\nDemande initiale du douanier:\n{user_input}"
    )
    logger.debug("start the send of the question")
    response = use_llm(enriched_prompt)
    logger.debug("finish the send of the question")
    return response