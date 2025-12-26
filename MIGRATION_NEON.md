# 🚀 Migration vers Neon PostgreSQL

Neon est une excellente alternative à Supabase pour PostgreSQL serverless. Il offre :
- ✅ Configuration plus simple
- ✅ Pas de problèmes IPv4/IPv6
- ✅ Connection pooling intégré
- ✅ Meilleure gestion des connexions
- ✅ Compatible avec psycopg2

## 📋 Étapes de Migration

### 1. Créer un Compte Neon

1. Allez sur [neon.tech](https://neon.tech)
2. Créez un compte (gratuit)
3. Créez un nouveau projet

### 2. Créer la Base de Données

1. Dans le dashboard Neon, créez une nouvelle base de données
2. Notez le **connection string** fourni par Neon
3. Il ressemble à : `postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require`

### 3. Exécuter le Schéma SQL

1. Copiez le contenu de `supabase_schema.sql`
2. Dans Neon → SQL Editor, exécutez le script
3. Vérifiez que toutes les tables sont créées

### 4. Configuration Streamlit Cloud

Dans **Streamlit Cloud** → **Settings** → **Secrets**, utilisez :

```toml
[database]
connection_string = "postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require"
```

**OU** avec paramètres individuels :

```toml
[database]
host = "ep-xxx-xxx.region.aws.neon.tech"
port = 5432
user = "user"
password = "password"
database = "dbname"
sslmode = "require"
```

## 🔧 Avantages de Neon

1. **Pas de problèmes IPv4/IPv6** : Neon gère automatiquement
2. **Connection pooling automatique** : Pas besoin de port spécial
3. **Configuration simple** : Juste une connection string
4. **Meilleure performance** : Optimisé pour serverless

## 📝 Notes

- Neon utilise le port standard **5432** (pas besoin de 6543)
- Le user est simple (pas besoin de `postgres.PROJECT_ID`)
- SSL est requis (`sslmode=require`)
- Le code existant devrait fonctionner sans modification majeure

