# 📋 Instructions pour Trouver le Hostname de Pooling

D'après votre capture d'écran, vous êtes sur la connection string **"Direct connection"** (port 5432). Nous avons besoin de la connection string de **pooling** (port 6543).

## 🔍 Étapes à Suivre

### 1. Dans la Modal "Connect to your project"

Vous voyez actuellement :
- **Type**: `URI`
- **Source**: `Primary Database`
- **Method**: `Direct connection` ← **CHANGEZ CECI**

### 2. Changer la Méthode

1. Cliquez sur le dropdown **"Method"**
2. Sélectionnez **"Transaction"** (ou **"Session"** si Transaction n'est pas disponible)
3. Cela devrait afficher une connection string avec le port **6543** et un hostname de pooling

### 3. Alternative : Utiliser le Bouton "Pooler settings"

Dans l'avertissement "Not IPv4 compatible", vous voyez un bouton **"Pooler settings"** :
1. Cliquez sur **"Pooler settings"**
2. Cela devrait vous montrer les options de pooling avec le hostname correct

### 4. Copier le Hostname de Pooling

Une fois que vous avez la connection string de pooling, elle devrait ressembler à :
```
postgresql://postgres.yrdhzpckptziyiefshga:[YOUR-PASSWORD]@HOSTNAME_POOLER:6543/postgres?pgbouncer=true
```

**COPIEZ EXACTEMENT** le hostname qui se trouve entre `@` et `:6543`

## 🔧 Configuration à Utiliser

Une fois le hostname de pooling trouvé, utilisez dans **Streamlit Cloud** → **Settings** → **Secrets** :

```toml
[database]
connection_string = "postgresql://postgres.yrdhzpckptziyiefshga:Douane20256@HOSTNAME_POOLER_EXACT:6543/postgres?pgbouncer=true"
```

**Remplacez** `HOSTNAME_POOLER_EXACT` par le hostname exact trouvé dans Supabase.

## ⚠️ Important

- Le hostname de pooling est **différent** du hostname direct
- Le hostname direct est : `db.yrdhzpckptziyiefshga.supabase.co` (port 5432)
- Le hostname de pooling sera quelque chose comme : `aws-0-eu-central-1.pooler.supabase.com` (port 6543)
- **COPIEZ EXACTEMENT** le hostname de pooling, ne l'inventez pas !

