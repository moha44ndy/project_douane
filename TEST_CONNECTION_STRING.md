# 🔧 Test avec Connection String Complète

L'erreur "Tenant or user not found" peut être résolue en utilisant une **connection string complète** au lieu de paramètres individuels.

## 📋 Configuration à Tester

Dans **Streamlit Cloud** → **Settings** → **Secrets**, essayez cette configuration :

### Option 1 : Connection String (RECOMMANDÉ)

```toml
[database]
connection_string = "postgresql://postgres.yrdhzpckptziyiefshga:Douane20256@aws-0-eu-central-1.pooler.supabase.com:6543/postgres?pgbouncer=true"
```

**Important** :
- La connection string doit être sur **UNE SEULE LIGNE**
- Remplacez `Douane20256` par votre mot de passe exact si différent
- Remplacez `aws-0-eu-central-1.pooler.supabase.com` par votre hostname de pooling exact

### Option 2 : Vérifier le Hostname Exact

Dans Supabase → **Settings** → **Database** → **Connection string** :

1. Cliquez sur **"Transaction"** (pour le pooling)
2. Cherchez la section **"Connection pooling"**
3. Le hostname peut être différent, par exemple :
   - `aws-0-eu-central-1.pooler.supabase.com`
   - `aws-1-eu-west-1.pooler.supabase.com`
   - Ou un autre selon votre région

4. **COPIEZ EXACTEMENT** le hostname affiché

### Option 3 : Utiliser le Hostname Direct (Sans Pooling)

Si le pooling ne fonctionne pas, essayez avec le port direct (peut avoir des problèmes IPv6) :

```toml
[database]
host = "db.yrdhzpckptziyiefshga.supabase.co"
port = 5432
user = "postgres"
password = "Douane20256"
database = "postgres"
```

**Note** : Le port 5432 peut avoir des problèmes IPv6 dans Streamlit Cloud, mais cela vaut la peine d'essayer.

## 🔍 Comment Trouver les Informations Exactes

1. **Hostname de Pooling** :
   - Supabase → Settings → Database
   - Section "Connection string"
   - Onglet "Transaction"
   - Cherchez `pooler.supabase.com` dans l'URL

2. **Projet ID** :
   - Supabase → Settings → General
   - Section "Reference ID"
   - C'est `yrdhzpckptziyiefshga` (confirmé)

3. **Mot de passe** :
   - Supabase → Settings → Database
   - Section "Database password"
   - Cliquez sur 👁️ pour voir
   - Copiez exactement (vérifiez les espaces)

## ⚠️ Si l'erreur persiste

1. Vérifiez que le projet Supabase n'est pas en pause
2. Vérifiez les restrictions réseau dans Supabase → Settings → Database → Network Restrictions
3. Essayez de vous connecter depuis Supabase SQL Editor pour vérifier que les identifiants fonctionnent
4. Contactez le support Supabase si nécessaire

