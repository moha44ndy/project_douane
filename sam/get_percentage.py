from rag import initialize_chatbot, process_user_input
from config.settings import Config
from sentence_transformers import SentenceTransformer, util
import textwrap
import json

def get_semantic_similarity(obtained, expected, model):
    """Calcule la similarité sémantique entre deux chaînes de caractères."""
    embeddings_obtained = model.encode(obtained, convert_to_tensor=True)
    embeddings_expected = model.encode(expected, convert_to_tensor=True)
    similarity = util.pytorch_cos_sim(embeddings_obtained, embeddings_expected)
    return similarity.item()

def save_results_to_file(results, filepath):
    """Sauvegarde les résultats dans un fichier avec une mise en page lisible."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("Résultats de l'évaluation du Chatbot\n")
        f.write("=" * 40 + "\n\n")
        for result in results:
            f.write(f"Question: {result['question']}\n")
            f.write(f"Réponse obtenue:\n{textwrap.fill(result['obtained'], width=70)}\n")
            f.write(f"Réponse attendue:\n{textwrap.fill(result['expected'], width=70)}\n")
            f.write(f"Pourcentage de similarité sémantique: {result['similarity']:.2f}%\n")
            f.write("-" * 40 + "\n\n")
        average_similarity = sum(r['similarity'] for r in results) / len(results)
        f.write(f"Moyenne des pourcentages de similarité sémantique: {average_similarity:.2f}%\n")

def normalize_obtained_text(raw_text):
    if not raw_text:
        return ""
    try:
        payload = json.loads(raw_text)
        narrative = payload.get("narrative", "")
        details = []
        for item in payload.get("classifications", []):
            snippet = f"{item.get('description','')} – {item.get('hs_code','')}"
            if item.get("dd_rate"):
                snippet += f" (D.D. {item.get('dd_rate')})"
            details.append(snippet.strip())
        parts = [narrative.strip()] + [d for d in details if d]
        return "\n".join(part for part in parts if part)
    except (json.JSONDecodeError, AttributeError):
        return raw_text


def main():
    # Initialiser le chatbot (charger les chunks, l'index, etc.)
    print("Initialisation du Chatbot...")
    chunks, emb, index, token = initialize_chatbot()
    print("Chatbot initialisé.\n")

    # Charger le modèle de sentence-transformers pour la similarité sémantique
    model = SentenceTransformer(Config.MODEL_DIR)

    # Liste courte de questions conformes au rôle douanier
    questions = [
        "Indique la position TEC/SH et le taux d'imposition pour du cacao en fèves non torréfiées.",
        "Classe un ordinateur portable assemblé en Côte d'Ivoire et donne le taux de droit de douane applicable.",
        "Donne la position et le taux pour un tissu contenant 65% coton et 35% polyester.",
    ]

    # Réponses attendues pour chaque question (même ordre que les questions)
    expected_answers = [
        "Les fèves de cacao non torréfiées relèvent de la position 1801.00 et supportent un droit TEC nul (matière première) avec TVA nationale standard.",
        "L'ordinateur portable se classe à la position 8471.30; le TEC prévoit un droit de 5% auquel s'ajoute la fiscalité intérieure.",
        "Le tissu 65% coton / 35% polyester se classe généralement en 5208/5209; il supporte un droit TEC d'environ 20% en raison de la prépondérance du coton.",
    ]

    # Liste pour stocker les résultats
    results = []

    # Poser les questions et comparer les réponses
    for question, expected in zip(questions, expected_answers):
        print(f"Question: {question}")
        obtained = process_user_input(question, chunks, emb, index, token)
        obtained_text = normalize_obtained_text(obtained)
        print(f"Réponse obtenue: {obtained_text}")
        print(f"Réponse attendue: {expected}")
        
        # Calculer le score de similarité sémantique
        similarity_score = get_semantic_similarity(obtained_text, expected, model) * 100
        results.append({
            'question': question,
            'obtained': obtained,
            'expected': expected,
            'similarity': similarity_score
        })

        print(f"Pourcentage de similarité sémantique: {similarity_score:.2f}%\n")

    # Sauvegarder les résultats dans un fichier
    save_results_to_file(results, 'chatbot_evaluation_results.txt')
    print("Résultats sauvegardés dans 'chatbot_evaluation_results.txt'.")

if __name__ == "__main__":
    main()
