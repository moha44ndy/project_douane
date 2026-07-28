# 🏛️ IA Classificateur CEDEAO

Une intelligence artificielle avancée pour la classification douanière selon le Système Harmonisé de la CEDEAO (Communauté Économique des États de l'Afrique de l'Ouest).

## 🎯 Objectif

Cette application permet de classifier automatiquement les produits selon le Tarif Extérieur Commun (TEC) de la CEDEAO en utilisant :

- **Analyse sémantique avancée** avec des modèles de traitement du langage naturel
- **Règles Générales d'Interprétation (RGI)** du Système Harmonisé
- **Base de données complète** du tarif douanier CEDEAO
- **Interface utilisateur moderne** et intuitive

## ✨ Fonctionnalités

### 🤖 IA Avancée
- **Analyse sémantique** : Compréhension du contexte et du sens des descriptions
- **Extraction de caractéristiques** : Matériaux, fonctions, spécifications techniques
- **Application des RGI** : Règles Générales d'Interprétation automatiques
- **Score de confiance** : Évaluation de la précision de la classification

### 📊 Classification Intelligente
- **Recherche multi-niveaux** : Sections, chapitres, sous-positions
- **Matching intelligent** : Correspondance basée sur la similarité sémantique
- **Suggestions d'amélioration** : Recommandations pour optimiser les descriptions
- **Explications détaillées** : Justification des classifications proposées

### 🧱 Architecture actuelle
- **Backend FastAPI** (`sam/api.py`) : moteur RAG, embeddings, FAISS, appel OpenAI.
- **Frontend Next.js** (`frontend/`) : pages `"/"` (classification), `"/historique"` et `"/admin"`.
- **Données locales** : `sam/table_data.json`, `sam/users.json`, index FAISS `sam/indexFaiss/local_index.faiss`.

L’ancienne interface Streamlit a été remplacée par cette architecture FastAPI + Next.js.
## Documentation technique

- [TECHNICAL_DOCUMENTATION.md](./TECHNICAL_DOCUMENTATION.md) : architecture, endpoints, environment variables, setup, deployment, and maintenance notes.
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) : client issues, priorities, root-cause analysis, and complete implementation roadmap.
- [IMPLEMENTATION_PROGRESS.md](./IMPLEMENTATION_PROGRESS.md) : running log of implemented fixes, causes, approach, and expected outcome.
- [CLIENT_DELIVERY_PROPOSAL.md](./CLIENT_DELIVERY_PROPOSAL.md) : client-facing summary of issues, improvement scope, expected outcome, and final deliverables.
- [CLIENT_CHANGE_SUMMARY.md](./CLIENT_CHANGE_SUMMARY.md) : final client handover document covering delivered changes, measured outcomes, validation, and scope limitations.
