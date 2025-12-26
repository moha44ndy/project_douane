# 🚀 Étapes pour Configurer Neon

Votre projet Neon "douane" est créé ! Voici les prochaines étapes :

## 📋 Étape 1 : Trouver la Connection String

1. Dans le sidebar gauche, cliquez sur **"production"** (sous BRANCH)
2. Cliquez sur **"Overview"**
3. Cherchez la section **"Connection string"** ou **"Connection details"**
4. Copiez la connection string complète (elle ressemble à) :
   ```
   postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require
   ```

**OU** si vous voyez des paramètres séparés :
- **Host**: `ep-xxx-xxx.region.aws.neon.tech`
- **Database**: `neondb` (ou autre nom)
- **User**: `neondb_owner` (ou autre)
- **Password**: (cliquez pour révéler)
- **Port**: `5432`

## 📋 Étape 2 : Exécuter le Schéma SQL

1. Dans le sidebar gauche, cliquez sur **"SQL Editor"** (sous production)
2. Ouvrez le fichier `supabase_schema.sql` dans votre éditeur local
3. Copiez tout le contenu du fichier
4. Collez-le dans l'éditeur SQL de Neon
5. Cliquez sur **"Run"** ou appuyez sur `Ctrl+Enter`
6. Vérifiez qu'il n'y a pas d'erreurs

## 📋 Étape 3 : Configurer Streamlit Cloud

Dans **Streamlit Cloud** → **Settings** → **Secrets**, utilisez :

### Option 1 : Connection String (RECOMMANDÉ)

```toml
[database]
connection_string = "postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require"
```

Remplacez par votre connection string Neon exacte.

### Option 2 : Paramètres Individuels

```toml
[database]
host = "ep-xxx-xxx.region.aws.neon.tech"
port = 5432
user = "neondb_owner"
password = "votre_mot_de_passe"
database = "neondb"
sslmode = "require"
```

## ✅ Avantages de Neon

- ✅ Pas de problèmes IPv4/IPv6
- ✅ Configuration simple
- ✅ Connection pooling automatique
- ✅ SSL automatique
- ✅ Pas besoin de `postgres.PROJECT_ID`

## 🔍 Où Trouver la Connection String dans Neon

1. **Méthode 1** : Dashboard → Overview → Connection string
2. **Méthode 2** : Settings → Connection details
3. **Méthode 3** : SQL Editor → Connection info (en haut)

Une fois que vous avez la connection string, mettez-la dans Streamlit Cloud secrets et testez !

