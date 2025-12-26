# 🔧 Corriger le Mot de Passe Admin dans Neon

Le problème est que le hash du mot de passe dans Neon est au format `$2y$` (bcrypt PHP), mais Python bcrypt utilise le format `$2b$`. Il faut régénérer le hash avec Python.

## 🔍 Solution : Mettre à Jour le Hash dans Neon

### Option 1 : Via l'Éditeur SQL de Neon (RECOMMANDÉ)

Dans l'éditeur SQL de Neon, exécutez cette requête pour mettre à jour le hash du mot de passe admin :

```sql
UPDATE users 
SET password_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYq5q5q5q5q'
WHERE identifiant_user = 'admin';
```

**ATTENTION** : Le hash ci-dessus est un exemple. Il faut générer un nouveau hash avec Python.

### Option 2 : Générer un Nouveau Hash avec Python

Exécutez ce script Python pour générer un nouveau hash :

```python
import bcrypt

password = "admin"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(hashed.decode('utf-8'))
```

Copiez le hash généré et utilisez-le dans la requête UPDATE ci-dessus.

### Option 3 : Réinitialiser le Mot de Passe via l'Application

1. Créez un script temporaire pour mettre à jour le mot de passe
2. Ou utilisez la fonction de changement de mot de passe dans l'application (si disponible)

## ✅ Vérification

Après avoir mis à jour le hash, testez la connexion avec :
- **Identifiant** : `admin`
- **Mot de passe** : `admin`

## 🔄 Alternative : Utiliser un Hash Compatible

Si vous préférez, vous pouvez aussi créer un nouvel utilisateur admin avec un mot de passe hashé correctement via l'application une fois que vous aurez accès.

