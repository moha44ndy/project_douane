# 🔍 Comment Trouver le Hostname de Pooling Exact dans Supabase

L'erreur "Tenant or user not found" indique que le **hostname de pooling** n'est probablement pas correct.

## 📋 Étapes pour Trouver le Hostname Exact

### 1. Accéder aux Paramètres de Base de Données

1. Connectez-vous à [Supabase](https://supabase.com)
2. Sélectionnez votre projet (`yrdhzpckptziyiefshga`)
3. Allez dans **Settings** (⚙️) → **Database**

### 2. Trouver la Connection String de Pooling

1. Dans la section **"Connection string"**, vous verrez plusieurs onglets :
   - **URI** (direct)
   - **JDBC** (direct)
   - **Transaction** (pooling) ← **C'EST CELUI-CI QU'IL FAUT**
   - **Session** (pooling)

2. Cliquez sur l'onglet **"Transaction"**

3. Vous verrez une connection string qui ressemble à :
   ```
   postgresql://postgres.yrdhzpckptziyiefshga:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres?pgbouncer=true
   ```

4. **COPIEZ EXACTEMENT** le hostname qui se trouve entre `@` et `:6543`
   - Dans cet exemple : `aws-0-eu-central-1.pooler.supabase.com`
   - **MAIS** votre hostname peut être différent !

### 3. Vérifier le Mot de Passe

1. Dans la même page **Settings** → **Database**
2. Cherchez **"Database password"**
3. Cliquez sur l'icône 👁️ pour **voir** le mot de passe
4. **COPIEZ EXACTEMENT** le mot de passe (attention aux espaces avant/après)

## 🔧 Configuration à Utiliser

Une fois que vous avez le hostname exact, utilisez cette configuration dans **Streamlit Cloud** → **Settings** → **Secrets** :

### Option 1 : Connection String Complète (RECOMMANDÉ)

```toml
[database]
connection_string = "postgresql://postgres.yrdhzpckptziyiefshga:VOTRE_MOT_DE_PASSE_EXACT@HOSTNAME_POOLER_EXACT:6543/postgres?pgbouncer=true"
```

**Remplacez** :
- `VOTRE_MOT_DE_PASSE_EXACT` par le mot de passe exact de Supabase
- `HOSTNAME_POOLER_EXACT` par le hostname exact trouvé dans Supabase

**Important** : La connection string doit être sur **UNE SEULE LIGNE**.

### Option 2 : Paramètres Individuels

```toml
[database]
host = "HOSTNAME_POOLER_EXACT"
port = 6543
user = "postgres.yrdhzpckptziyiefshga"
password = "VOTRE_MOT_DE_PASSE_EXACT"
database = "postgres"
```

**Remplacez** :
- `HOSTNAME_POOLER_EXACT` par le hostname exact trouvé dans Supabase
- `VOTRE_MOT_DE_PASSE_EXACT` par le mot de passe exact de Supabase

## ⚠️ Points Importants

1. **Le hostname peut être différent** : `aws-0-eu-central-1.pooler.supabase.com` est un exemple, mais votre hostname peut être :
   - `aws-1-eu-west-1.pooler.supabase.com`
   - `aws-0-us-east-1.pooler.supabase.com`
   - Ou un autre selon votre région

2. **Le mot de passe doit être exact** : Copiez-le depuis Supabase (icône 👁️), ne le tapez pas manuellement

3. **Le projet ID est correct** : `yrdhzpckptziyiefshga` (confirmé)

## 🆘 Si l'erreur persiste après avoir trouvé le hostname exact

1. Vérifiez que votre projet Supabase n'est pas en pause
2. Vérifiez les restrictions réseau dans **Settings** → **Database** → **Network Restrictions**
3. Essayez de vous connecter depuis **Supabase SQL Editor** pour vérifier que les identifiants fonctionnent
4. Contactez le support Supabase si nécessaire

