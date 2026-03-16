import glob
import faiss
import numpy as np
import pathlib
import requests
import os
import re
from .config.settings import Config
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain_community.document_loaders import PyPDFLoader
from requests.auth import HTTPBasicAuth
import urllib3
import json
from openai import OpenAI

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Nouveau client OpenAI (SDK >= 1.x)
client = OpenAI(api_key=Config.OPENAI_API_KEY)

# Configuration embeddings / modèles
EMBEDDING_MODEL = Config.EMBEDDING_MODEL or "text-embedding-3-large"

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
        print(f"[OK] {len(chunks)} chunks charges depuis le fichier")
        return chunks

    documents = []
    print("start load doc in document")
    
    contrat_dir = os.path.join(rag_dir, "contrat")
    
    # Vérifier que le dossier existe
    if not os.path.exists(contrat_dir):
        raise FileNotFoundError(f"Le dossier 'contrat' n'existe pas! Chemin recherche: {contrat_dir}")
    
    # Vérifier qu'il y a des fichiers PDF
    pdf_files = glob.glob(os.path.join(contrat_dir, "*.pdf"))
    if not pdf_files:
        raise FileNotFoundError("Aucun fichier PDF trouve dans le dossier 'contrat'!")
    
    print(f"[OK] {len(pdf_files)} fichiers PDF trouves")
    
    for file in pdf_files:
        try:
            print(f"  Chargement de {file}...")
            loader = PyPDFLoader(file)
            documents += loader.load()
        except Exception as e:
            print(f"[ERREUR] Fichier '{file}': {e}")
    
    if not documents:
        raise ValueError("Aucun document n'a pu etre charge!")
    
    print(f"[OK] {len(documents)} documents charges")
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
        raise ValueError("Aucun chunk cree apres le splitting!")
    
    print(f"[OK] {len(chunks)} chunks crees")
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
        raise ValueError("Aucun chunk disponible!")
    
    print(f"[OK] {len(chunks)} chunks disponibles")
    print("finish loading document and create chunks")

    if os.path.exists(index_path):
        # Charger l'index directement depuis le fichier FAISS (chemin pre-bâti)
        index = faiss.read_index(index_path)
        print(f"[OK] Index charge depuis le fichier existant ({index.ntotal} vecteurs)")
    else:
        # Créer un nouvel index en utilisant les embeddings OpenAI
        print("start the creation of the faiss index (OpenAI embeddings)")
        index = create_faiss_index(chunks)
        print("finish the creation of the faiss index")

    return chunks, index


def create_faiss_index(chunks):
    """Créer un index FAISS à partir des chunks."""
    
    # VÉRIFICATIONS CRITIQUES
    if not chunks:
        raise ValueError("Liste de chunks vide!")
    
    print(f"Generation des embeddings OpenAI pour {len(chunks)} chunks...")
    
    # Extraire le texte des chunks
    chunk_texts = [chunk.page_content for chunk in chunks]
    
    # Vérifier qu'il y a du contenu
    if not chunk_texts or not chunk_texts[0]:
        raise ValueError("Les chunks ne contiennent pas de texte!")
    
    print(f"Premier chunk (100 premiers caracteres): {chunk_texts[0][:100]}...")
    
    # Générer les embeddings via l'API OpenAI (batch)
    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=chunk_texts,
        )
        chunk_vectors = [d.embedding for d in response.data]
    except Exception as e:
        print(f"[ERREUR] Generation des embeddings OpenAI: {e}")
        raise
    
    # Vérifier que les embeddings ont été générés
    if not chunk_vectors or len(chunk_vectors) == 0:
        raise ValueError("Aucun embedding genere!")
    
    print(f"[OK] {len(chunk_vectors)} embeddings generes")
    print(f"[OK] Dimension des embeddings: {len(chunk_vectors[0])}")
    
    # Convertir en array numpy
    chunk_vectors_array = np.array(chunk_vectors).astype('float32')
    
    # Créer l'index FAISS
    dimension = chunk_vectors_array.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(chunk_vectors_array)
    
    print(f"[OK] Index FAISS cree avec {index.ntotal} vecteurs")
    
    # Obtenir le répertoire du fichier rag.py
    rag_dir = os.path.dirname(os.path.abspath(__file__))
    index_dir = os.path.join(rag_dir, "indexFaiss")
    
    # Créer le dossier si nécessaire
    os.makedirs(index_dir, exist_ok=True)
    
    # Sauvegarder l'index
    index_path = os.path.join(index_dir, "local_index.faiss")
    faiss.write_index(index, index_path)
    print(f"[OK] Index sauvegarde dans '{index_path}'")
    
    return index


def search_faiss_index(query, index, k=5):
    print("start vectorisation de la requete (OpenAI embeddings)")
    try:
        resp = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[query],
        )
        query_vector = np.array(resp.data[0].embedding).astype("float32")
    except Exception as e:
        print(f"[ERREUR] Embedding de la requete: {e}")
        raise
    print("finish vectorisation de la requete")
    print("start research of index by similarity")
    distances, indices = index.search(np.array([query_vector]), k)
    print("finish research of index by similarity")
    return indices, distances

# Use the LLM API
def use_llm(prompt_text):
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
            "Retourne exclusivement un objet JSON unique (aucun texte en dehors du JSON) respectant le schéma "
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
            "Si tu dois faire une déduction, indique-le dans \"justification\"."
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


def process_user_input(user_input, chunks, index):
    queries = split_user_queries(user_input)
    if not queries:
        return "Merci de préciser au moins une marchandise à classifier."

    prompt_sections = []
    for i, query in enumerate(queries, start=1):
        context = build_context_for_query(query, chunks, index)
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
    response = use_llm(enriched_prompt)
    print("finish the send of the question")
    return response