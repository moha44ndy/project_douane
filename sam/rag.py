import glob
import faiss
import numpy as np
import pathlib
from pathlib import Path
import requests
import os
import re
import hashlib
from config.settings import Config
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from requests.auth import HTTPBasicAuth
import urllib3
import json
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from openai import OpenAI

# Importer l'exception Streamlit pour les secrets
try:
    from streamlit.errors import StreamlitSecretNotFoundError
except ImportError:
    # Pour les versions plus anciennes de Streamlit
    StreamlitSecretNotFoundError = Exception

# Importer le module de cache Redis
try:
    from cache_redis import (
        get_from_cache,
        set_to_cache,
        delete_from_cache,
        clear_cache,
        get_cache_stats,
        is_redis_available
    )
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ Module cache_redis non disponible, utilisation du cache local")

# Charger le .env depuis la racine du projet
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Fallback to default .env location

# Variable globale pour le client OpenAI (initialisée de manière paresseuse)
_client = None

# Cache local de fallback (si Redis n'est pas disponible)
# Utiliser session_state pour persister entre les pages
_local_cache = None

def get_local_cache():
    """Obtient le cache local depuis session_state (fallback si Redis n'est pas disponible)"""
    import streamlit as st
    global _local_cache
    if "_local_cache" not in st.session_state:
        st.session_state["_local_cache"] = {}
    return st.session_state["_local_cache"]

def get_openai_client():
    """Obtient le client OpenAI, en le créant si nécessaire."""
    global _client
    if _client is None:
        # Essayer d'abord Streamlit secrets (pour production)
        api_key = None
        try:
            import streamlit as st
            if hasattr(st, 'secrets'):
                try:
                    # Tenter d'accéder aux secrets (peut lever StreamlitSecretNotFoundError)
                    secrets = st.secrets
                    if 'OPENAI_API_KEY' in secrets:
                        api_key = secrets['OPENAI_API_KEY']
                    elif 'openai' in secrets and 'api_key' in secrets['openai']:
                        api_key = secrets['openai']['api_key']
                except StreamlitSecretNotFoundError:
                    # Fichier secrets.toml non trouvé, utiliser .env
                    pass
                except (KeyError, AttributeError, TypeError):
                    # Erreur lors de l'accès aux secrets, utiliser .env
                    pass
        except ImportError:
            pass
        
        # Sinon, utiliser les variables d'environnement
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY n'est pas définie. "
                "Veuillez configurer cette variable d'environnement dans le fichier .env "
                "ou dans les paramètres de Streamlit Cloud (secrets)."
            )
        _client = OpenAI(api_key=api_key)
    return _client
# Configuration
from_code = "en"
to_code = "fr"
#AUTH_URL = Config.AUTH_URL
#API_URL = Config.API_URL
#USERNAME = Config.USER
#PASSWORD = Config.PASSWORD
MODEL_DIR = Config.MODEL_DIR or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
#MODEL_ID = Config.MODEL_ID

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
        print("Chargement des chunks à partir du fichier.")
        chunks = load_chunks(chunks_filepath)
        print(f"✅ {len(chunks)} chunks chargés depuis le fichier")
        return chunks

    documents = []
    print("start load doc in document")
    
    contrat_dir = os.path.join(rag_dir, "contrat")
    
    # Vérifier que le dossier existe
    if not os.path.exists(contrat_dir):
        raise FileNotFoundError(f"❌ Le dossier 'contrat' n'existe pas! Chemin recherché: {contrat_dir}")
    
    # Vérifier qu'il y a des fichiers PDF
    pdf_files = glob.glob(os.path.join(contrat_dir, "*.pdf"))
    if not pdf_files:
        raise FileNotFoundError("❌ Aucun fichier PDF trouvé dans le dossier 'contrat'!")
    
    print(f"📄 {len(pdf_files)} fichiers PDF trouvés")
    
    for file in pdf_files:
        try:
            print(f"  Chargement de {file}...")
            loader = PyPDFLoader(file)
            documents += loader.load()
        except Exception as e:
            print(f"❌ Erreur survenue pour le fichier '{file}': {e}")
    
    if not documents:
        raise ValueError("❌ Aucun document n'a pu être chargé!")
    
    print(f"✅ {len(documents)} documents chargés")
    print("finish load doc in document")
    print("start the translate")
    print("finish the translate")   
    
    # Diviser les documents en chunks
    print("start the splitting of the text")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600, 
        chunk_overlap=120, 
        length_function=len, 
        separators=["\n\n", "\n", "."]
    )
    chunks = text_splitter.split_documents(documents=documents)
    
    if not chunks:
        raise ValueError("❌ Aucun chunk créé après le splitting!")
    
    print(f"✅ {len(chunks)} chunks créés")
    print("finish the splitting of the text")
    
    save_chunks(chunks, chunks_filepath)
    return chunks

def initialize_chatbot():
    faiss.omp_set_num_threads(3)
    # Obtenir le répertoire du fichier rag.py
    rag_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(rag_dir, "indexFaiss", "local_index.faiss")
    
    # Toujours créer les chunks
    print("start loading document and create chunks")
    chunks = load_documents_and_create_chunks()
    
    if not chunks:
        raise ValueError("❌ Aucun chunk disponible!")
    
    print(f"✅ {len(chunks)} chunks disponibles")
    print("finish loading document and create chunks")
    
    print("🤖 Chargement du modèle d'embeddings...")
    try:
        # Optimiser le chargement du modèle pour réduire l'utilisation mémoire
        emb = HuggingFaceEmbeddings(
            model_name=MODEL_DIR, 
            encode_kwargs={"normalize_embeddings": True},
            model_kwargs={"device": "cpu", "trust_remote_code": False}  # Forcer l'utilisation du CPU
        )
    except OSError as e:
        if "1455" in str(e) or "pagination" in str(e).lower() or "paging" in str(e).lower():
            error_msg = """
            ❌ ERREUR DE MÉMOIRE VIRTUELLE
            
            Le fichier de pagination Windows est insuffisant pour charger le modèle.
            
            Solutions :
            1. Augmenter le fichier de pagination Windows :
               - Panneau de configuration > Système > Paramètres système avancés
               - Performance > Paramètres > Avancé > Mémoire virtuelle
               - Augmenter la taille du fichier d'échange (recommandé : 2x la RAM)
            
            2. Fermer d'autres applications pour libérer de la mémoire
            
            3. Redémarrer l'ordinateur pour libérer la mémoire
            """
            raise RuntimeError(error_msg) from e
        else:
            raise

    if os.path.exists(index_path):
        # Charger l'index directement depuis le fichier FAISS
        index = faiss.read_index(index_path)
        print(f"✅ Index chargé depuis le fichier existant ({index.ntotal} vecteurs)")
    else:
        # Créer un nouvel index
        print("start the creation of the faiss index")
        index = create_faiss_index(chunks, emb)
        print("finish the creation of the faiss index")
    
    return chunks, emb, index

def create_faiss_index(chunks, emb):
    """Créer un index FAISS à partir des chunks."""
    
    # VÉRIFICATIONS CRITIQUES
    if not chunks:
        raise ValueError("❌ Liste de chunks vide!")
    
    print(f"🔄 Génération des embeddings pour {len(chunks)} chunks...")
    
    # Extraire le texte des chunks
    chunk_texts = [chunk.page_content for chunk in chunks]
    
    # Vérifier qu'il y a du contenu
    if not chunk_texts or not chunk_texts[0]:
        raise ValueError("❌ Les chunks ne contiennent pas de texte!")
    
    print(f"📝 Premier chunk (100 premiers caractères): {chunk_texts[0][:100]}...")
    
    # Générer les embeddings en batch (plus efficace)
    try:
        chunk_vectors = emb.embed_documents(chunk_texts)
    except Exception as e:
        print(f"❌ Erreur lors de la génération des embeddings: {e}")
        raise
    
    # Vérifier que les embeddings ont été générés
    if not chunk_vectors or len(chunk_vectors) == 0:
        raise ValueError("❌ Aucun embedding généré!")
    
    print(f"✅ {len(chunk_vectors)} embeddings générés")
    print(f"✅ Dimension des embeddings: {len(chunk_vectors[0])}")
    
    # Convertir en array numpy
    chunk_vectors_array = np.array(chunk_vectors).astype('float32')
    
    # Créer l'index FAISS
    dimension = chunk_vectors_array.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(chunk_vectors_array)
    
    print(f"✅ Index FAISS créé avec {index.ntotal} vecteurs")
    
    # Obtenir le répertoire du fichier rag.py
    rag_dir = os.path.dirname(os.path.abspath(__file__))
    index_dir = os.path.join(rag_dir, "indexFaiss")
    
    # Créer le dossier si nécessaire
    os.makedirs(index_dir, exist_ok=True)
    
    # Sauvegarder l'index
    index_path = os.path.join(index_dir, "local_index.faiss")
    faiss.write_index(index, index_path)
    print(f"✅ Index sauvegardé dans '{index_path}'")
    
    return index

def search_faiss_index(query, emb, index, k=5):
    print("start vectorisation de la requete")
    query_vector = np.array(emb.embed_query(query)).astype('float32')
    print("finish vectorisation de la requete")
    print("start research of index by similarity")
    distances, indices = index.search(np.array([query_vector]), k)
    print("finish research of index by similarity")
    return indices, distances

# Use the LLM API
def use_llm(prompt_text, user_query=None):
    """
    Utilise le LLM pour générer une réponse
    user_query: La requête originale de l'utilisateur (pour validation préventive)
    """
    # Utiliser la requête utilisateur normalisée comme clé de cache
    if user_query:
        # Normaliser la requête utilisateur (minuscules, suppression espaces multiples)
        normalized_query = ' '.join(user_query.lower().strip().split())
        cache_query = normalized_query
    else:
        # Fallback: utiliser le prompt complet si pas de user_query
        cache_query = prompt_text
    
    # Vérifier si le cache doit être invalidé (requêtes similaires notées négativement)
    if user_query and REDIS_AVAILABLE:
        try:
            from feedback_db import should_invalidate_cache
            if should_invalidate_cache(user_query):
                print("⚠️ Cache invalidé: requête similaire notée négativement")
                # Invalider le cache pour cette requête (Redis)
                delete_from_cache(cache_query)
        except Exception as e:
            print(f"Erreur lors de la vérification du cache: {e}")
    
    # Essayer de récupérer depuis le cache Redis (partagé entre tous les utilisateurs)
    if REDIS_AVAILABLE:
        cached_response = get_from_cache(cache_query)
        if cached_response:
            return cached_response
    
    # Fallback: utiliser le cache local (session_state) si Redis n'est pas disponible
    if not REDIS_AVAILABLE or not is_redis_available():
        local_cache = get_local_cache()
        cache_key = hashlib.sha256(cache_query.encode('utf-8')).hexdigest()
        
        if cache_key in local_cache:
            print("✅ Réponse récupérée depuis le cache local")
            return local_cache[cache_key]
    
    try:
        system_instruction = (
            "Tu es un assistant AI nommé Mosam conçu pour aider des douaniers à troiuver les prix à fixer sur les produits "
            "RGI 1: Les titres des sections, chapitres et sous-chapitres n'ont qu'une valeur indicative."

"RGI 2: Les marchandises incomplètes ou non finies sont classées comme complètes."

"RGI 3: Le mélange ou l'assemblage de matières ou d'articles est classé selon la matière prépondérante."

"RGI 4: Les marchandises qui ne peuvent être classées selon les règles 1 à 3 sont classées dans la position la plus analogue."

"RGI 5: Les emballages sont classés avec les marchandises qu'ils contiennent."

"RGI 6: Le classement des marchandises dans les sous-positions d'une même position est déterminé selon les termes de ces sous-positions."
            "Réponds uniquement aux questions posées. Tu ne peux pas fournir de réponse si "
            "l'information n'est pas explicitement présente dans les documents. "
            "Mosam est une équipe juridique, donc tu ne peux pas inventer de réponse. "
            "Priorise la clarté et la concision. "
            "Ne mentionne jamais des documents : fais comme si les infos étaient internes. "
            "Si la question sort du périmètre Mosam, rappelle le périmètre. "
            "Si tu n'as pas la réponse, demande des précisions. "
            "Réponds dans la langue du prompt suivant. "
            "Chaque réponse doit, pour chaque marchandise, indiquer explicitement la position tarifaire "
            "du TEC/SH, le ou les taux d'imposition applicables (droits de douane, TVA, autres taxes "
            "si disponibles) et une justification synthétique (RGI, notes, critères techniques). "
            "S'il y a plusieurs marchandises, structure la réponse sous forme de tableau ou de liste "
            "séparée, une ligne par marchandise. "
            "Si le terme exact n'apparaît pas dans les documents, tente immédiatement plusieurs synonymes "
            "ou variantes (par exemple: \"barre métallique\", \"barre en fer\", \"barre en acier\", "
            "\"produit sidérurgique\"). "
            "Si malgré ces variantes aucune mention explicite n'est trouvée, réalise une déduction en t'appuyant "
            "sur les RGI et sur la logique du TEC CEDEAO, en signalant clairement qu'il s'agit d'une "
            "déduction fondée sur les règles."
            "Dans les documents sources, interprète les abréviations suivantes: "
            "\"D.D.\" = droits de douane, \"R.S.\" = régime statistique (taxe statistique), "
            "\"U.S.\" = unité de mesure et \"N.T.S.\" = numéro tarifaire supplémentaire. "
            "Quand tu cites ces abréviations, ajoute toujours la définition entre parenthèses, "
            "par exemple \"D.D. (droits de douane)\". "
            "IMPORTANT - Format de réponse: " 
            "- Si la question concerne la classification d'un produit spécifique, retourne exclusivement un objet JSON unique (aucun texte en dehors du JSON) respectant le schéma " 
            "suivant: {\"narrative\":\"texte synthétique pour le douanier\",\"classifications\":[{" 
            "\"description\":\"Résumé de la marchandise\",\"hs_code\":\"8517.13.00.00\"," 
            "\"section\":\"XVI\",\"chapter\":\"85\",\"dd_rate\":\"5 %\",\"rs_rate\":\"1 %\"," 
            "\"us_unit\":\"PIÈCE\",\"other_taxes\":\"TVA 18 %\"," 
            "\"justification\":\"Synthèse RGI / critères\",\"excerpt\":\"Citation exacte du document\"," 
            "\"origin\":\"USA\",\"value\":\"Non renseigné\",\"confidence\":92}]}. " 
            "Chaque objet de \"classifications\" doit contenir au minimum ces champs; utilise " 
            "\"Non renseigné\" si une donnée manque et veille à ce que \"chapter\" soit toujours sur deux chiffres " 
            "et \"confidence\" un nombre entre 0 et 100. Le champ \"description\" doit reprendre le nom précis " 
            "du produit classé tel qu'énoncé par le douanier (ou une reformulation très courte), afin de pouvoir " 
            "l'afficher directement dans le tableau de suivi. " 
            "Si tu dois faire une déduction, indique-le dans \"justification\". " 
            "- Si la question est générale (explication, information, question sur les RGI, etc.) et ne concerne PAS la classification d'un produit spécifique, " 
            "retourne un objet JSON avec uniquement {\"narrative\":\"ta réponse textuelle complète\",\"classifications\":[]}. " 
            "Dans ce cas, fournis une réponse claire et complète dans le champ \"narrative\" sans essayer de créer des classifications."
        )

        client = get_openai_client()
        response = client.responses.create(
            model="gpt-5-nano",
            input=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt_text}
            ],
            store=True
        )

        response_text = response.output_text
        
        # Mettre en cache la réponse (Redis partagé ou cache local)
        if REDIS_AVAILABLE and is_redis_available():
            # Cache Redis partagé (TTL de 7 jours par défaut)
            # Les règles douanières changent rarement, donc 7 jours est approprié
            set_to_cache(cache_query, response_text, ttl=604800)  # 7 jours = 604800 secondes
        else:
            # Fallback: cache local (session_state)
            local_cache = get_local_cache()
            cache_key = hashlib.sha256(cache_query.encode('utf-8')).hexdigest()
            local_cache[cache_key] = response_text
            print("💾 Réponse mise en cache local")
        
        return response_text

    except Exception as e:
        return f"Erreur lors de l'appel au modèle OpenAI : {e}"

def clear_api_cache():
    """Vide le cache des réponses API (Redis et cache local)"""
    # Vider le cache Redis
    if REDIS_AVAILABLE and is_redis_available():
        deleted_count = clear_cache("cache:llm:*")
        if deleted_count > 0:
            print(f"🧹 {deleted_count} entrée(s) supprimée(s) du cache Redis")
        else:
            print("🧹 Cache Redis vidé")
    
    # Vider le cache local (fallback)
    import streamlit as st
    if "_local_cache" in st.session_state:
        st.session_state["_local_cache"].clear()
        print("🧹 Cache local vidé")

def get_cache_stats():
    """Retourne les statistiques du cache (Redis ou local)"""
    if REDIS_AVAILABLE and is_redis_available():
        # Statistiques Redis
        from cache_redis import get_cache_stats as get_redis_stats
        return get_redis_stats()
    else:
        # Statistiques cache local
        local_cache = get_local_cache()
        return {
            "enabled": False,
            "size": len(local_cache),
            "status": "Cache local (Redis non disponible)"
        }

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


def build_context_for_query(query, chunks, emb, index):
    """Génère un contexte documentaire pour une requête précise."""
    indices, _ = search_faiss_index(query, emb, index)
    context = ""
    for idx in indices[0]:
        context += chunks[idx].page_content + "\n"
    return context


def is_general_question(user_input):
    """Détecte si la question est générale (pas de classification de produit)"""
    general_keywords = [
        "qu'est-ce que", "c'est quoi", "explique", "comment fonctionne", "quelle est la différence",
        "pourquoi", "quand", "où", "qui", "définition", "signifie", "signification", "rgi", "règles générales",
        "qu'est-ce qu'une", "qu'est-ce qu'un", "qu'est-ce qu'", "qu'est ce que", "qu'est ce qu'",
        "aide", "help", "assistance", "information", "informations", "explication", "expliquer"
    ]
    user_lower = user_input.lower().strip()
    
    # Si la question commence par un mot-clé général
    for keyword in general_keywords:
        if user_lower.startswith(keyword) or f" {keyword}" in user_lower:
            return True
    
    # Si la question contient "?" et pas de nom de produit évident
    if "?" in user_input and len(user_input.split()) < 10:
        # Vérifier si ça ressemble à une question générale
        question_words = ["quoi", "comment", "pourquoi", "quand", "où", "qui", "quel", "quelle", "quels", "quelles"]
        first_words = user_lower.split()[:3]
        if any(word in question_words for word in first_words):
            return True
    
    return False

def process_user_input(user_input, chunks, emb, index):
    """
    Traite l'entrée utilisateur avec validation préventive
    """
    # Détecter si c'est une question générale
    is_general = is_general_question(user_input)
    
    if is_general:
        # Pour les questions générales, construire un prompt différent
        context = build_context_for_query(user_input, chunks, emb, index)
        enriched_prompt = (
            f"Question du douanier: {user_input}\n\n"
            f"Contexte documentaire disponible:\n{context}\n\n"
            "Réponds à cette question de manière claire et complète en t'appuyant sur le contexte documentaire. "
            "Si la question ne concerne pas la classification d'un produit spécifique, retourne uniquement "
            "un objet JSON avec {\"narrative\":\"ta réponse textuelle complète\",\"classifications\":[]}."
        )
    else:
        # Traitement normal pour les classifications de produits
        queries = split_user_queries(user_input)
        if not queries:
            return "Merci de préciser au moins une marchandise à classifier.", None

        # VALIDATION PRÉVENTIVE: Vérifier les feedbacks négatifs similaires
        warning_message = None
        try:
            from feedback_db import check_similar_negative_feedbacks
            similar_feedbacks = check_similar_negative_feedbacks(user_input, similarity_threshold=0.6)
            
            if similar_feedbacks:
                # Construire un message d'avertissement
                feedback_count = sum(f['count'] for f in similar_feedbacks)
                warning_message = (
                    f"⚠️ ATTENTION: {feedback_count} requête(s) similaire(s) ont reçu des notes négatives récemment. "
                    f"Veuillez vérifier attentivement la réponse."
                )
                print(f"⚠️ Validation préventive: {len(similar_feedbacks)} feedback(s) négatif(s) similaire(s) détecté(s)")
                
                # Ajouter un contexte d'avertissement dans le prompt
                warning_context = "\n\n⚠️ ATTENTION IMPORTANTE: Des requêtes similaires ont reçu des feedbacks négatifs. "
                warning_context += "Sois particulièrement attentif à la précision et à la justesse de ta réponse. "
                warning_context += "Vérifie bien les codes tarifaires, les taux et les justifications.\n"
        except Exception as e:
            print(f"Erreur lors de la validation préventive: {e}")
            warning_message = None

        prompt_sections = []
        for i, query in enumerate(queries, start=1):
            context = build_context_for_query(query, chunks, emb, index)
            prompt_sections.append(
                f"[MARCHANDISE {i}]\nDescription: {query}\nContexte documentaire:\n{context}"
            )

        combined_context = "\n\n".join(prompt_sections)
        
        # Ajouter l'avertissement au prompt si nécessaire
        warning_prefix = warning_context if warning_message else ""
        
        enriched_prompt = (
            warning_prefix +
            "Le douanier peut avoir fourni plusieurs marchandises. "
            "Analyse chaque bloc ci-dessous et produis une réponse structurée avec, pour chaque marchandise, "
            "la position tarifaire, le taux d'imposition et les détails pertinents.\n\n"
            f"{combined_context}\n\nDemande initiale du douanier:\n{user_input}"
        )
    
    print("start the send of the question")
    # Passer user_input pour la validation du cache
    response = use_llm(enriched_prompt, user_query=user_input)
    print("finish the send of the question")
    
    # Retourner la réponse avec le message d'avertissement si nécessaire
    # Le message d'avertissement sera géré dans app.py
    if is_general:
        return response, None  # Pas de warning pour les questions générales
    else:
        return response, warning_message