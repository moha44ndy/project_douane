import glob
import faiss
import numpy as np
import argostranslate.package
import argostranslate.translate
import pathlib
import requests
import os
import re
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

# Configuration
from_code = "en"
to_code = "fr"
package_path = pathlib.Path(Config.ARGOS_MODEL)
argostranslate.package.install_from_path(package_path)
AUTH_URL = Config.AUTH_URL
API_URL = Config.API_URL
USERNAME = Config.USER
PASSWORD = Config.PASSWORD
MODEL_DIR = Config.MODEL_DIR
MODEL_ID = Config.MODEL_ID

def save_chunks(chunks, filepath):
    """Sauvegarder les chunks dans un fichier JSON."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump([doc.page_content for doc in chunks], f, indent=4)

def load_chunks(filepath):
    """Charger les chunks à partir d'un fichier JSON."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = json.load(f)
    return [Document(page_content=chunk) for chunk in content]

def get_auth_token(auth_url, username, password):
    """Obtenir un token d'authentification."""
    try:
        payload = {'grant_type': 'client_credentials'}
        response = requests.post(
            auth_url,
            auth=HTTPBasicAuth(username, password),
            data=payload,
            verify=False
        )
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            print(f"Erreur lors de l'authentification: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception lors de l'authentification: {e}")
        return None

# Load documents and create FAISS index
def load_documents_and_create_chunks():
    """Charger les documents, les traduire et les diviser en chunks."""

    chunks_filepath = "chunks.json"
    if os.path.exists(chunks_filepath):
        print("Chargement des chunks à partir du fichier.")
        return load_chunks(chunks_filepath)

    documents = []
    print("start load doc in document")
    for file in glob.glob("contrat/*.pdf"):
        try:
            loader = PyPDFLoader(file)
            documents += loader.load()
        except Exception as e:
            print(f"Erreur survenue pour le fichier '{file}': {e}")
    print("finish load doc in document")
    print("start the translate")
    for doc in documents:
        doc.page_content = argostranslate.translate.translate(doc.page_content, from_code, to_code)
    print("finish the translate")   
    # Diviser les documents en chunks
    print("start the splitting of the text")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=120, length_function=len, separators=["\n\n", "\n", "."])
    chunks = text_splitter.split_documents(documents=documents)
    print("finish the splitting of the text")
    save_chunks(chunks, chunks_filepath)
    return chunks

def initialize_chatbot():
    faiss.omp_set_num_threads(3)
    index_path = "indexFaiss/local_index.faiss"
    
    # Toujours créer les chunks
    print("start loading document and create chunks")
    chunks = load_documents_and_create_chunks()
    print("finish loading document and create chunks")
    emb = HuggingFaceEmbeddings(model_name=MODEL_DIR, encode_kwargs={"normalize_embeddings": True})

    if os.path.exists(index_path):
        # Charger l'index directement depuis le fichier FAISS
        index = faiss.read_index(index_path)
        print("Index chargé depuis le fichier existant.")
    else:
        # Créer un nouvel index
        print("start the creation of the faiss index")
        index = create_faiss_index(chunks, emb)
        print("finish the creation of the faiss index")
    
    print("start get token")
    token = get_auth_token(AUTH_URL, USERNAME, PASSWORD)
    print("finish get token")
    return chunks, emb, index, token

def create_faiss_index(chunks, emb):
    chunk_vectors = [np.array(emb.embed_query(chunk.page_content)).astype('float32') for chunk in chunks]
    print(f"Dimension des embeddings des chunks : {chunk_vectors[0].shape}")
    chunk_vectors_array = np.array(chunk_vectors).astype('float32')
    dimension = chunk_vectors_array.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(chunk_vectors_array)
    faiss.write_index(index, 'indexFaiss/local_index.faiss')
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
def use_llm(api_url, token, model_id, prompt_text):
    try:
        system_instruction = (
            "Tu es Mosam, un assistant douanier spécialisé dans la classification tarifaire "
            "de la CEDEAO. Tu aides les équipes à appliquer les Règles Générales "
            "d'Interprétation (RGI), à identifier les positions du Système Harmonisé et à "
            "fournir des explications juridiques fiables. Réponds uniquement si "
            "l'information figure explicitement dans les documents fournis ou dans ta base "
            "interne. Ne divulgue jamais la provenance des documents, rappelle le périmètre "
            "douanier quand une question en sort, reste concis et clair, et détecte "
            "automatiquement la langue du dernier message utilisateur pour y répondre. "
            "Pour chaque marchandise, donne la position tarifaire TEC/SH, le ou les taux "
            "d'imposition applicables (droits, TVA, autres taxes si disponibles) et une "
            "justification synthétique. Quand plusieurs marchandises sont demandées en même "
            "temps, structure la réponse avec une ligne par marchandise (tableau ou liste). "
            "Si le terme fourni n'existe pas tel quel dans les documents, teste plusieurs synonymes ou "
            "formulations proches (par exemple \"barre métallique\", \"barre en fer\", \"barre en acier\"). "
            "En dernier recours, procède à une déduction argumentée en t'appuyant sur les RGI et "
            "le TEC CEDEAO et précise qu'il s'agit d'une déduction. "
            "Dans les documents PDF, interprète les abréviations: \"D.D.\" = droits de douane, "
            "\"R.S.\" = régime/statistique, \"U.S.\" = unité de mesure et \"N.T.S.\" = numéro tarifaire supplémentaire. "
            "Chaque fois que tu mentionnes ces sigles, écris la définition entre parenthèses, "
            "par exemple \"R.S. (régime/statistique)\". "
            "Retourne exclusivement un objet JSON unique (aucun texte hors JSON) de la forme "
            "{\"narrative\":\"texte pour le douanier\",\"classifications\":[{\"description\":\"...\","
            "\"hs_code\":\"8517.13.00.00\",\"section\":\"XVI\",\"chapter\":\"85\",\"dd_rate\":\"5 %\","
            "\"rs_rate\":\"1 %\",\"us_unit\":\"PIÈCE\",\"other_taxes\":\"TVA 18 %\","
            "\"justification\":\"...\",\"excerpt\":\"...\",\"origin\":\"USA\",\"value\":\"Non renseigné\","
            "\"confidence\":90}]}. "
            "Renseigne tous ces champs (utilise \"Non renseigné\" si besoin) et assure-toi que \"chapter\" comporte deux chiffres "
            "et que \"confidence\" est un nombre entre 0 et 100. Le champ \"description\" doit correspondre au nom exact "
            "du produit classé tel que soumis par le douanier (ou une reformulation concise utilisable telle quelle dans un tableau)."
        )
        payload = {
            "modelId": model_id,
            "input": {
                "systemInstructions": [
                    {"text": (system_instruction + " Prends en compte ces remarques et notifie les également")}
                ],
                "contents": [
                    {"text": prompt_text}
                ]
            },
            "generationConfig": {
                "topP": 0.9,
                "temperature": 0.5,
                "maxCandidates": 1,
                "outputMaxTokens": 1000
            }
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        response = requests.post(api_url, json=payload, headers=headers, verify=False)
        if response.status_code in [200, 201]:
            api_response = response.json()
            response_text = api_response['candidates'][0]['text']
            return response_text
        else:
            return f"Erreur API: {response.status_code}, Détails: {response.text}"
    except Exception as e:
        return f"Erreur lors de l'appel à l'API: {e}"

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
    indices, _ = search_faiss_index(query, emb, index)
    context = ""
    for idx in indices[0]:
        context += chunks[idx].page_content + "\n"
    return context


def process_user_input(user_input, chunks, emb, index, token):
    queries = split_user_queries(user_input)
    if not queries:
        return "Merci de préciser au moins une marchandise à classifier."

    prompt_sections = []
    for i, query in enumerate(queries, start=1):
        context = build_context_for_query(query, chunks, emb, index)
        prompt_sections.append(
            f"[MARCHANDISE {i}]\nDescription: {query}\nContexte documentaire:\n{context}"
        )

    combined_context = "\n\n".join(prompt_sections)
    enriched_prompt = (
        "Le douanier peut avoir fourni plusieurs marchandises. "
        "Analyse chaque bloc ci-dessous et produis une réponse structurée avec, pour chaque marchandise, "
        "la position tarifaire, le taux d'imposition et les détails pertinents.\n\n"
        f"{combined_context}\n\nDemande initiale du douanier:\n{user_input}"
    )
    print("start the send of the question")
    response = use_llm(API_URL, token, MODEL_ID, enriched_prompt)
    print("finish the send of the question") 
    return response
