# ✅ Vérifier l'Utilisateur Admin dans Neon

Le schéma SQL a été exécuté avec succès ! Vérifions que l'utilisateur admin a été créé.

## 🔍 Vérification dans l'Éditeur SQL

Dans l'éditeur SQL de Neon, exécutez cette requête :

```sql
SELECT user_id, nom_user, identifiant_user, email, statut, is_admin
FROM users
WHERE identifiant_user = 'admin';
```

### Résultat Attendu

Vous devriez voir un utilisateur avec :
- **identifiant_user** : `admin`
- **nom_user** : `Administrateur Système`
- **email** : `admin@douane.ci`
- **statut** : `actif`
- **is_admin** : `true` (ou `TRUE`)

## 🔐 Identifiants de Connexion

Si l'utilisateur admin existe, vous pouvez vous connecter à l'application avec :
- **Identifiant** : `admin`
- **Mot de passe** : `admin`

## ⚠️ Si l'Utilisateur Admin n'Existe Pas

Si la requête ne retourne aucun résultat, l'utilisateur admin n'a pas été créé. Dans ce cas, exécutez cette requête dans l'éditeur SQL de Neon :

```sql
INSERT INTO users (nom_user, identifiant_user, email, password_hash, statut, is_admin)
VALUES (
    'Administrateur Système',
    'admin',
    'admin@douane.ci',
    '$2y$10$vMJTyG/p853epmwAVWXtB.IuW9m1edNeb3KCG3KyAKcYUU9.8WK02', -- Hashed password for 'admin'
    'actif',
    TRUE
) ON CONFLICT (identifiant_user) DO NOTHING;
```

Cette requête créera l'utilisateur admin s'il n'existe pas déjà.

## ✅ Une Fois Vérifié

1. Les tables sont créées ✅
2. L'utilisateur admin est créé ✅
3. Vous pouvez vous connecter à l'application avec `admin` / `admin`

Testez maintenant la connexion dans votre application Streamlit !

