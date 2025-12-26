# ⚡ Déploiement Rapide - Mosam

## 🎯 Étapes rapides pour déployer sur Streamlit Cloud

### 1. Préparer le repository
```bash
# Assurez-vous que tous les fichiers sont commités
git add .
git commit -m "Prepare for deployment"
git push
```

### 2. Déployer sur Streamlit Cloud

1. Allez sur https://share.streamlit.io
2. Connectez votre compte GitHub
3. Cliquez sur "New app"
4. Sélectionnez votre repository : `project_douane`
5. **Main file path** : `sam/app.py`
6. Cliquez sur "Deploy"

### 3. Configurer les secrets

Dans Streamlit Cloud → Settings → Secrets, ajoutez :

```toml
[database]
host = "votre-host"
port = 3306
user = "votre-user"
password = "votre-password"
database = "douane_simple"

OPENAI_API_KEY = "sk-..."
```

### 4. Vérifier les fichiers nécessaires

Assurez-vous que ces fichiers sont dans le repository :
- ✅ `sam/indexFaiss/local_index.faiss`
- ✅ `sam/contrat/MON TEC CEDEAO SH 2022 FREN-09 04 2024.pdf`
- ✅ `sam/requirements.txt`
- ✅ `.streamlit/config.toml`

### 5. Tester

Une fois déployé, testez :
- Connexion à la base de données
- Classification d'un produit
- Navigation entre les pages

## 📝 Notes

- Streamlit Cloud redéploie automatiquement à chaque push sur main
- Les logs sont disponibles dans l'interface Streamlit Cloud
- Pour les gros fichiers (FAISS), utilisez Git LFS si nécessaire

