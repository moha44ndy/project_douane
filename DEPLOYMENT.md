# 🚀 Guide de Déploiement - Mosam CEDEAO

Ce guide explique comment déployer l'application Mosam sur Streamlit Cloud.

## 📋 Prérequis

1. **Compte Streamlit Cloud** : Créez un compte sur [share.streamlit.io](https://share.streamlit.io)
2. **Repository GitHub** : Votre code doit être sur GitHub
3. **Base de données MySQL** : Accès à une base de données MySQL (locale ou cloud)
4. **Clé API OpenAI** : Pour les fonctionnalités LLM

## 🔧 Configuration

### 1. Préparer le repository

Assurez-vous que votre repository contient :
- `sam/app.py` (point d'entrée principal)
- `sam/requirements.txt` (dépendances Python)
- `.streamlit/config.toml` (configuration Streamlit)
- Tous les fichiers nécessaires (indexFaiss, PDF, etc.)

### 2. Déployer sur Streamlit Cloud

1. **Connecter votre repository** :
   - Allez sur [share.streamlit.io](https://share.streamlit.io)
   - Cliquez sur "New app"
   - Connectez votre compte GitHub
   - Sélectionnez votre repository `project_douane`

2. **Configurer l'application** :
   - **Main file path** : `sam/app.py`
   - **Python version** : 3.11 (recommandé)

3. **Configurer les secrets** :
   - Dans l'interface Streamlit Cloud, allez dans "Settings" → "Secrets"
   - Ajoutez les secrets suivants (voir `.streamlit/secrets.toml.example`) :

```toml
[database]
host = "votre-host-mysql"
port = 3306
user = "votre-utilisateur-mysql"
password = "votre-mot-de-passe-mysql"
database = "douane_simple"

OPENAI_API_KEY = "votre-clé-api-openai"

AUTH_URL = "votre-auth-url"
API_URL = "votre-api-url"
USER = "votre-user"
PASSWORD = "votre-password"
MODEL_DIR = "votre-model-dir"
MODEL_ID = "votre-model-id"
ARGOS_MODEL = "votre-argos-model"
```

### 3. Variables d'environnement alternatives

Si vous préférez utiliser des variables d'environnement au lieu de secrets.toml, vous pouvez les configurer dans Streamlit Cloud :
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `OPENAI_API_KEY`
- `AUTH_URL`, `API_URL`, `USER`, `PASSWORD`, `MODEL_DIR`, `MODEL_ID`, `ARGOS_MODEL`

## 📁 Fichiers nécessaires

L'application nécessite les fichiers suivants dans le repository :

- `sam/indexFaiss/local_index.faiss` : Index FAISS pour la recherche vectorielle
- `sam/contrat/MON TEC CEDEAO SH 2022 FREN-09 04 2024.pdf` : Document PDF source
- `sam/chunks.json` : Chunks de documents (optionnel, peut être régénéré)

## 🗄️ Base de données

### Option 1 : Base de données cloud

Utilisez un service MySQL cloud comme :
- **PlanetScale**
- **AWS RDS**
- **Google Cloud SQL**
- **Azure Database for MySQL**

### Option 2 : Base de données locale avec tunnel

Si vous avez une base de données locale, utilisez un tunnel SSH ou un service comme :
- **ngrok** (pour MySQL)
- **Cloudflare Tunnel**

## 🔍 Vérification post-déploiement

1. Vérifiez que l'application démarre sans erreur
2. Testez la connexion à la base de données
3. Testez une classification de produit
4. Vérifiez que les fichiers FAISS sont accessibles

## 🐛 Dépannage

### Erreur de connexion à la base de données
- Vérifiez que les credentials dans secrets.toml sont corrects
- Vérifiez que la base de données est accessible depuis Internet
- Vérifiez les règles de firewall

### Erreur "Module not found"
- Vérifiez que `requirements.txt` contient toutes les dépendances
- Vérifiez que le chemin du fichier principal est correct (`sam/app.py`)

### Erreur "File not found" pour FAISS ou PDF
- Vérifiez que les fichiers sont bien commités dans Git
- Vérifiez les chemins relatifs dans le code

## 📝 Notes importantes

- Les fichiers volumineux (FAISS index, PDF) doivent être dans le repository Git
- Pour les très gros fichiers, considérez l'utilisation de Git LFS
- Streamlit Cloud a des limites de mémoire et de CPU selon le plan
- Le cache RAG est stocké en session_state et ne persiste pas entre les redémarrages

## 🔄 Mise à jour

Pour mettre à jour l'application :
1. Poussez vos modifications sur GitHub
2. Streamlit Cloud redéploiera automatiquement
3. Ou déclenchez manuellement un redéploiement depuis l'interface

