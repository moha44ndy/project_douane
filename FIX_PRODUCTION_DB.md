# 🔧 Fix : Erreur de Connexion en Production (Streamlit Cloud)

## 🎯 Problème
Erreur "impossible de se connecter à la base de données" en production (Streamlit Cloud).

## ✅ Solution : Configurer les Secrets dans Streamlit Cloud

### Étape 1 : Ouvrir Streamlit Cloud

1. Allez sur [share.streamlit.io](https://share.streamlit.io)
2. Connectez-vous avec votre compte GitHub
3. Ouvrez votre application **project_douane**

### Étape 2 : Configurer les Secrets

1. Cliquez sur **⚙️ Settings** (en haut à droite)
2. Cliquez sur **Secrets** dans le menu de gauche
3. **Supprimez** tout ce qui existe déjà dans la section `[database]` (s'il y en a)
4. **Ajoutez** cette configuration complète :

```toml
[database]
connection_string = "postgresql://postgres:Douane2025#@db.yrdhzpckptziyiefshga.supabase.co:5432/postgres"
```

**OU** avec paramètres individuels :

```toml
[database]
host = "db.yrdhzpckptziyiefshga.supabase.co"
port = 5432
user = "postgres"
password = "Douane2025#"
database = "postgres"
```

### Étape 3 : Sauvegarder et Redéployer

1. Cliquez sur **Save** en bas de la page
2. L'application va **redéployer automatiquement**
3. Attendez 1-2 minutes pour le redéploiement
4. Rafraîchissez la page de l'application

## 🔍 Vérifications

### 1. Vérifier que les Secrets sont Sauvegardés

Dans Streamlit Cloud → Settings → Secrets, vous devriez voir :
```
[database]
connection_string = "postgresql://..."
```

### 2. Vérifier les Logs

Dans Streamlit Cloud :
1. Cliquez sur **☰ Menu** (hamburger en haut à gauche)
2. Cliquez sur **Manage app**
3. Allez dans l'onglet **Logs**
4. Cherchez les erreurs de connexion

### 3. Vérifier Supabase

Dans Supabase :
1. Allez dans **Table Editor**
2. Vérifiez que les tables existent :
   - `users`
   - `classifications`
   - `historique`

## 🐛 Dépannage

### Erreur "password authentication failed"

**Cause** : Mot de passe incorrect dans les secrets

**Solution** :
1. Vérifiez le mot de passe dans Supabase → Settings → Database
2. Cliquez sur l'icône 👁️ pour voir le mot de passe
3. Copiez-le exactement (sans espaces)
4. Mettez à jour les secrets dans Streamlit Cloud

### Erreur "connection refused" ou "timeout"

**Cause** : Host ou port incorrect

**Solution** :
1. Vérifiez dans Supabase → Settings → Database → Connection info
2. Utilisez le **host exact** : `db.yrdhzpckptziyiefshga.supabase.co`
3. Utilisez le **port 5432** (ou 6543 pour pooling)

### Erreur "relation does not exist"

**Cause** : Le schéma SQL n'a pas été exécuté

**Solution** :
1. Dans Supabase → **SQL Editor**
2. Copiez le contenu de `supabase_schema.sql`
3. Exécutez le script
4. Vérifiez dans **Table Editor** que les tables existent

### L'application ne redéploie pas

**Solution** :
1. Dans Streamlit Cloud → **Manage app**
2. Cliquez sur **⋮** (trois points) → **Reboot app**
3. Ou faites un commit vide sur GitHub pour forcer le redéploiement

## 📋 Configuration Complète Recommandée

Pour Streamlit Cloud → Settings → Secrets :

```toml
[database]
connection_string = "postgresql://postgres:Douane2025#@db.yrdhzpckptziyiefshga.supabase.co:5432/postgres"

# Clé API OpenAI (si nécessaire)
OPENAI_API_KEY = "votre-clé-openai"
```

## ✅ Checklist

- [ ] Secrets configurés dans Streamlit Cloud
- [ ] Connection string correcte (avec bon mot de passe)
- [ ] Application redéployée
- [ ] Tables créées dans Supabase
- [ ] Logs vérifiés (pas d'erreurs)
- [ ] Test de connexion dans l'application

## 🆘 Si Rien ne Fonctionne

1. **Vérifiez que le projet Supabase est actif** (pas en pause)
2. **Réinitialisez le mot de passe** dans Supabase → Settings → Database → Reset database password
3. **Utilisez la nouvelle connection string** dans Streamlit Cloud
4. **Vérifiez les logs** pour des erreurs spécifiques

