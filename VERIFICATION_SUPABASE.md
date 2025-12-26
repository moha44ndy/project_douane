# 🔍 Vérification de la Configuration Supabase

L'erreur "Tenant or user not found" indique un problème de configuration. Vérifiez **EXACTEMENT** ces informations dans Supabase :

## 📋 Étapes de Vérification

### 1. Vérifier le Hostname de Pooling

Dans Supabase → **Settings** → **Database** → **Connection string** :

1. Cliquez sur **"Transaction"** (pas "Session" ni "Direct")
2. Cherchez la section **"Connection pooling"**
3. Le hostname devrait ressembler à : `aws-0-eu-central-1.pooler.supabase.com`
4. **COPIEZ EXACTEMENT** ce hostname (il peut être différent pour votre projet)

### 2. Vérifier le Projet ID (Project Ref)

Dans Supabase → **Settings** → **General** :

1. Cherchez **"Reference ID"** ou **"Project ID"**
2. C'est une chaîne de caractères comme : `yrdhzpckptziyiefshga`
3. **COPIEZ EXACTEMENT** cet ID

### 3. Vérifier le Mot de Passe

Dans Supabase → **Settings** → **Database** :

1. Cherchez **"Database password"**
2. Cliquez sur l'icône 👁️ pour **voir** le mot de passe
3. **COPIEZ EXACTEMENT** le mot de passe (attention aux espaces, majuscules/minuscules)

### 4. Configuration Recommandée

Dans **Streamlit Cloud** → **Settings** → **Secrets**, utilisez :

```toml
[database]
host = "VOTRE_HOSTNAME_POOLER_EXACT"
port = 6543
user = "postgres.VOTRE_PROJECT_ID_EXACT"
password = "VOTRE_MOT_DE_PASSE_EXACT"
database = "postgres"
```

**Exemple** (remplacez par vos valeurs exactes) :
```toml
[database]
host = "aws-0-eu-central-1.pooler.supabase.com"
port = 6543
user = "postgres.yrdhzpckptziyiefshga"
password = "Douane20256"
database = "postgres"
```

## ⚠️ Points Importants

1. **Hostname** : Doit être le hostname de **pooling** (port 6543), pas le hostname direct (port 5432)
2. **User** : Format exact `postgres.PROJECT_ID` (avec le point)
3. **Password** : Copiez exactement depuis Supabase (pas d'espaces avant/après)
4. **Port** : Toujours `6543` pour le pooling

## 🔄 Alternative : Utiliser Connection String

Si les paramètres individuels ne fonctionnent pas, essayez avec une connection string :

```toml
[database]
connection_string = "postgresql://postgres.VOTRE_PROJECT_ID:VOTRE_MOT_DE_PASSE@VOTRE_HOSTNAME_POOLER:6543/postgres?pgbouncer=true"
```

**Important** : La connection string doit être sur **UNE SEULE LIGNE**.

## 🆘 Si l'erreur persiste

1. Vérifiez que votre projet Supabase n'est pas en pause
2. Vérifiez les restrictions réseau dans Supabase → Settings → Database → Network Restrictions
3. Essayez de vous connecter depuis Supabase SQL Editor pour vérifier que les identifiants fonctionnent
4. Contactez le support Supabase si nécessaire

