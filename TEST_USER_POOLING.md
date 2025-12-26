# 🔧 Test : Format du User pour le Pooling Supabase

## 🎯 Problème

Erreur "Tenant or user not found" même avec :
- ✅ User : `postgres.yrdhzpckptziyiefshga`
- ✅ Hostname : `aws-0-eu-central-1.pooler.supabase.com`
- ✅ Port : 6543
- ✅ Mot de passe : `Douane20256`

## ✅ Solution à Tester

Pour le pooling Supabase, le format du user peut être différent. Essayons avec juste `postgres` :

### Configuration à Tester dans Streamlit Cloud → Settings → Secrets :

```toml
[database]
host = "aws-0-eu-central-1.pooler.supabase.com"
port = 6543
user = "postgres"
password = "Douane20256"
database = "postgres"
```

**Note** : User = juste `postgres` (sans le projet ID) pour le pooling.

## 🔍 Autres Possibilités

Si cela ne fonctionne pas, le problème pourrait être :
1. Le mot de passe n'est toujours pas correct
2. Le projet Supabase a des restrictions réseau
3. Le pooling n'est pas activé correctement

## 📋 Vérifications

1. Vérifiez que le mot de passe est exactement `Douane20256` (sans espaces)
2. Vérifiez que le projet Supabase n'est pas en pause
3. Vérifiez les "Network Restrictions" dans Supabase → Settings → Database

