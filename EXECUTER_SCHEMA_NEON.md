# 📋 Exécuter le Schéma SQL dans Neon

L'erreur "relation 'users' does not exist" indique que les tables n'ont pas encore été créées dans Neon.

## 🔧 Étapes pour Exécuter le Schéma

### 1. Ouvrir l'Éditeur SQL dans Neon

1. Connectez-vous à [Neon Console](https://console.neon.tech)
2. Sélectionnez votre projet "douane"
3. Dans le sidebar gauche, cliquez sur **"production"** (sous BRANCH)
4. Cliquez sur **"SQL Editor"**

### 2. Copier le Contenu du Schéma

1. Ouvrez le fichier `neon_schema.sql` dans votre éditeur local
2. **Sélectionnez TOUT le contenu** (Ctrl+A)
3. **Copiez** (Ctrl+C)

### 3. Exécuter dans Neon

1. Dans l'éditeur SQL de Neon, **collez** le contenu (Ctrl+V)
2. Cliquez sur le bouton **"Run"** ou appuyez sur `Ctrl+Enter`
3. Attendez que l'exécution se termine
4. Vérifiez qu'il n'y a **pas d'erreurs** dans les résultats

### 4. Vérifier les Tables

1. Dans le sidebar gauche, cliquez sur **"Tables"** (sous production)
2. Vous devriez voir les tables suivantes :
   - ✅ `users`
   - ✅ `classifications`
   - ✅ `historique`
   - ✅ Et les autres tables du schéma

## ⚠️ Si vous avez des Erreurs

### Erreur "type already exists"
- C'est normal si vous avez déjà exécuté une partie du schéma
- Les types ENUM peuvent déjà exister
- Continuez l'exécution, les autres parties devraient fonctionner

### Erreur "relation already exists"
- Les tables existent déjà
- Vérifiez dans "Tables" si elles sont présentes
- Si oui, le schéma est déjà exécuté

### Erreur de syntaxe
- Vérifiez que vous avez copié tout le fichier
- Assurez-vous qu'il n'y a pas de caractères manquants

## ✅ Une fois le Schéma Exécuté

1. Les tables seront créées
2. L'utilisateur admin sera créé avec :
   - Identifiant : `admin`
   - Mot de passe : `admin`
3. Vous pourrez vous connecter à l'application

## 🔍 Vérification Rapide

Dans l'éditeur SQL de Neon, exécutez cette requête pour vérifier :

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public';
```

Vous devriez voir toutes les tables listées.

