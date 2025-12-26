# 🔧 Fix : Utiliser le Port de Pooling Supabase

## 🎯 Problème

L'erreur "Cannot assign requested address" avec IPv6 persiste même avec la résolution IPv4.

## ✅ Solution : Utiliser le Port de Pooling (6543)

Supabase offre un port de pooling (6543) qui peut mieux gérer les connexions depuis Streamlit Cloud.

### Configuration dans Streamlit Cloud → Settings → Secrets

**Option A : Port de Pooling (RECOMMANDÉ)**

```toml
[database]
host = "db.yrdhzpckptziyiefshga.supabase.co"
port = 6543
user = "postgres"
password = "Douane2025#"
database = "postgres"
```

**Option B : Connection String avec Pooling**

```toml
[database]
connection_string = "postgresql://postgres:Douane2025%23@db.yrdhzpckptziyiefshga.supabase.co:6543/postgres?pgbouncer=true"
```

## 📋 Étapes

1. Allez dans **Streamlit Cloud** → **Settings** → **Secrets**
2. Remplacez le port `5432` par `6543`
3. OU utilisez la connection string avec `pgbouncer=true`
4. Cliquez sur **Save**
5. Attendez le redéploiement

## 🔍 Différence entre les Ports

- **Port 5432** : Connexion directe à PostgreSQL (peut avoir des problèmes IPv6)
- **Port 6543** : Connection pooling via PgBouncer (meilleure compatibilité)

