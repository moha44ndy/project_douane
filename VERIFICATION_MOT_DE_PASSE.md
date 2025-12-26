# 🔐 Vérification du Mot de Passe Supabase

## 🎯 Problème Actuel

- ✅ IPv4 résolu avec le pooling (`aws-0-eu-central-1.pooler.supabase.com`)
- ✅ User correct : `postgres.yrdhzpckptziyiefshga`
- ❌ Erreur "Tenant or user not found"

Cette erreur peut signifier :
1. **Mot de passe incorrect**
2. **Format du user incorrect pour le pooling**
3. **Projet Supabase en pause ou problème de configuration**

## ✅ Solution : Vérifier le Mot de Passe

### Étape 1 : Récupérer le Mot de Passe Exact

1. Allez dans **Supabase** → **Settings** → **Database**
2. Dans la section **Connection info** ou **Database password**
3. Cliquez sur l'icône 👁️ pour **voir le mot de passe**
4. **Copiez-le exactement** (sans espaces avant/après)

### Étape 2 : Vérifier le Format du User pour le Pooling

Pour le pooling Supabase, le format peut être :
- `postgres.yrdhzpckptziyiefshga` (avec le projet ID)
- OU juste `postgres` (selon la configuration)

### Étape 3 : Configuration dans Streamlit Cloud

**Option A : Avec le user complet (recommandé)**

```toml
[database]
host = "aws-0-eu-central-1.pooler.supabase.com"
port = 6543
user = "postgres.yrdhzpckptziyiefshga"
password = "[MOT_DE_PASSE_EXACT_DE_SUPABASE]"
database = "postgres"
```

**Option B : Avec juste postgres (à essayer si A ne fonctionne pas)**

```toml
[database]
host = "aws-0-eu-central-1.pooler.supabase.com"
port = 6543
user = "postgres"
password = "[MOT_DE_PASSE_EXACT_DE_SUPABASE]"
database = "postgres"
```

## 🔍 Autres Vérifications

1. **Vérifier que le projet n'est pas en pause** dans Supabase
2. **Vérifier que les tables existent** (exécuter `supabase_schema.sql` si nécessaire)
3. **Vérifier la connection string exacte** dans Supabase → Settings → Database → Connection string → "Connection pooling"

## 📋 Connection String de Pooling (Session Mode)

Si Supabase fournit une connection string exacte, utilisez-la :

```toml
[database]
connection_string = "[CONNECTION_STRING_EXACTE_DE_SUPABASE]"
```

Copiez la connection string **exacte** depuis Supabase (elle contient déjà le bon format de user et password).

