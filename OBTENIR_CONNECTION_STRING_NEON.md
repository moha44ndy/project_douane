# 🔗 Comment Obtenir la Connection String Neon

Vous êtes sur la page "Branch overview". Voici comment obtenir la connection string :

## 📋 Méthode 1 : Via le Bouton "Connect" (RECOMMANDÉ)

1. Dans la section **"Primary Database"**, vous voyez :
   - ID: `ep-broad-surf-a47iws9q`
   - Status: **ACTIVE** (point vert)
   - Bouton **"Connect"** (bouton noir)

2. **Cliquez sur le bouton "Connect"**

3. Une modal ou un panneau s'ouvrira avec :
   - La **connection string complète**
   - Ou les **paramètres individuels** (host, port, user, password, database)

4. **Copiez la connection string complète** (elle ressemble à) :
   ```
   postgresql://user:password@ep-broad-surf-a47iws9q.region.aws.neon.tech/neondb?sslmode=require
   ```

## 📋 Méthode 2 : Via SQL Editor

1. Dans le sidebar gauche, cliquez sur **"SQL Editor"**
2. En haut de l'éditeur SQL, cherchez **"Connection info"** ou **"Connection string"**
3. Copiez la connection string

## 📋 Méthode 3 : Via Settings

1. Dans le sidebar gauche, cliquez sur **"Settings"** (sous PROJECT)
2. Cherchez la section **"Connection details"** ou **"Database connection"**
3. Copiez la connection string

## ✅ Une fois la Connection String Obtenue

1. **Exécutez le schéma SQL** :
   - Cliquez sur **"SQL Editor"** dans le sidebar
   - Ouvrez `supabase_schema.sql` dans votre éditeur
   - Copiez tout le contenu et collez-le dans l'éditeur SQL de Neon
   - Cliquez sur **"Run"**

2. **Configurez Streamlit Cloud** :
   - Allez dans Streamlit Cloud → Settings → Secrets
   - Utilisez cette configuration :

```toml
[database]
connection_string = "postgresql://user:password@ep-broad-surf-a47iws9q.region.aws.neon.tech/neondb?sslmode=require"
```

Remplacez par votre connection string exacte.

## 🔍 Informations Importantes

- **Host**: `ep-broad-surf-a47iws9q.region.aws.neon.tech` (ou similaire)
- **Port**: `5432` (standard)
- **Database**: `neondb` (ou autre nom)
- **User**: `neondb_owner` (ou autre)
- **Password**: (révélé dans la connection string)
- **SSL**: `sslmode=require` (toujours requis)

Une fois que vous avez la connection string, exécutez le schéma SQL et configurez Streamlit Cloud !

