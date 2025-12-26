# 🚀 Guide Complet Supabase - Mosam CEDEAO

Guide complet pour configurer et utiliser Supabase avec l'application Mosam.

## 📋 Table des Matières

1. [Configuration Initiale](#configuration-initiale)
2. [Configuration Streamlit Cloud](#configuration-streamlit-cloud)
3. [Détection Automatique MySQL/PostgreSQL](#détection-automatique)
4. [Dépannage](#dépannage)

---

## 🔧 Configuration Initiale

### Étape 1 : Créer le Projet Supabase

1. Allez sur [supabase.com](https://supabase.com)
2. Créez un nouveau projet
3. Notez votre identifiant de projet (ex: `yrdhzpckptziyiefshga`)

### Étape 2 : Exécuter le Schéma SQL

1. Dans Supabase → **SQL Editor**
2. Copiez le contenu de `supabase_schema.sql`
3. Exécutez le script

Les tables suivantes seront créées :
- ✅ `users` (avec utilisateur admin par défaut)
- ✅ `classifications`
- ✅ `historique`
- ✅ Types ENUM, fonctions, vues

### Étape 3 : Récupérer les Informations de Connexion

Dans Supabase → **Settings** → **Database** :

- **Host** : `db.xxxxx.supabase.co`
- **Port** : `5432` (direct) ou `6543` (pooling)
- **User** : `postgres`
- **Password** : Cliquez sur 👁️ pour le voir
- **Database** : `postgres`

---

## ☁️ Configuration Streamlit Cloud

### Option 1 : Connection String (Recommandé)

Dans Streamlit Cloud → **Settings** → **Secrets** :

```toml
[database]
connection_string = "postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres"
```

**Remplacez** :
- `[PASSWORD]` par votre mot de passe Supabase
- `db.xxxxx.supabase.co` par votre host Supabase

### Option 2 : Paramètres Individuels

```toml
[database]
host = "db.xxxxx.supabase.co"
port = 5432
user = "postgres"
password = "votre-mot-de-passe"
database = "postgres"
```

### Option 3 : Connection Pooling

Pour de meilleures performances, utilisez le connection pooling :

```toml
[database]
connection_string = "postgresql://postgres.xxxxx:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres"
```

Récupérez cette connection string dans Supabase → Settings → Database → Connection pooling.

---

## 🔄 Détection Automatique MySQL/PostgreSQL

L'application détecte automatiquement le type de base de données :

### En Local (MySQL)
- Port `3306` → MySQL
- Utilise `database_mysql.py`

### En Production (Supabase/PostgreSQL)
- Port `5432` ou connection string avec "postgresql" → PostgreSQL
- Utilise `database_postgresql.py`

### Configuration Locale

Dans votre `.env` :

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=votre-mot-de-passe
DB_NAME=douane_simple
```

### Forcer un Type Spécifique

```env
DB_TYPE=mysql      # Force MySQL
# ou
DB_TYPE=postgresql # Force PostgreSQL
```

Voir `LOCAL_VS_PRODUCTION.md` pour plus de détails.

---

## 🐛 Dépannage

### Erreur "connection refused"
- Vérifiez que le host, port, user, password sont corrects
- Vérifiez que votre projet Supabase est actif
- Vérifiez que votre IP est autorisée dans Supabase

### Erreur "password authentication failed"
- Vérifiez que le mot de passe est correct (sans espaces)
- Réinitialisez le mot de passe dans Supabase si nécessaire

### Erreur "relation does not exist"
- Vérifiez que le schéma SQL a été exécuté
- Vérifiez que vous êtes connecté à la bonne base (`postgres`)

### Timeout en Local
- Normal si vous testez depuis votre machine locale
- Streamlit Cloud devrait fonctionner car il a accès direct à Supabase

### Mauvaise Détection de Type
- Forcez le type avec `DB_TYPE` dans votre `.env`
- Vérifiez les ports (3306 = MySQL, 5432 = PostgreSQL)

---

## ✅ Checklist

- [ ] Projet Supabase créé
- [ ] Schéma SQL exécuté (`supabase_schema.sql`)
- [ ] Tables créées (`users`, `classifications`, `historique`)
- [ ] Utilisateur admin présent
- [ ] Informations de connexion récupérées
- [ ] Secrets configurés dans Streamlit Cloud
- [ ] Application redéployée
- [ ] Connexion testée avec succès

---

## 📚 Ressources

- [Documentation Supabase](https://supabase.com/docs)
- [Documentation PostgreSQL](https://www.postgresql.org/docs/)
- [Streamlit Secrets](https://docs.streamlit.io/streamlit-cloud/get-started/deploy-an-app/connect-to-data-sources/secrets-management)

---

## 🔐 Sécurité

- ⚠️ **Ne commitez JAMAIS** vos mots de passe dans Git
- ⚠️ Utilisez les **Secrets** de Streamlit Cloud pour les informations sensibles
- ⚠️ Changez le mot de passe admin par défaut (`admin` / `admin`) en production

