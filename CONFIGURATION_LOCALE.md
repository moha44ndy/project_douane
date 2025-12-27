# Configuration locale - Guide de dépannage

## Problème de connexion en local

Si vous n'arrivez plus à vous connecter en local mais que ça fonctionne en production, suivez ce guide.

## Solution : Fichier .env

Le fichier `.env` a été créé à la racine du projet. Vous devez le configurer avec vos paramètres MAMP.

### 1. Localiser le fichier .env

Le fichier se trouve à : `c:\MAMP\htdocs\project_douane\.env`

### 2. Configurer les paramètres MAMP

Ouvrez le fichier `.env` et modifiez les valeurs suivantes selon votre configuration MAMP :

#### Pour MySQL (MAMP standard)

```env
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306          # Ou 8889 selon votre version de MAMP
DB_USER=root
DB_PASSWORD=          # Votre mot de passe MySQL (peut être vide)
DB_NAME=douane_simple
```

#### Ports MAMP courants :
- **MAMP standard** : Port `3306` (MySQL standard)
- **MAMP PRO** : Port `3306` ou `8889`
- **MAMP avec configuration personnalisée** : Vérifiez dans les préférences MAMP

#### Pour trouver votre configuration MAMP :

1. Ouvrez MAMP
2. Cliquez sur "Préférences" ou "Preferences"
3. Allez dans l'onglet "Ports"
4. Notez le port MySQL (généralement 3306 ou 8889)
5. Pour le mot de passe :
   - Ouvrez phpMyAdmin depuis MAMP
   - Essayez de vous connecter avec `root` et un mot de passe vide
   - Si ça ne fonctionne pas, le mot de passe est probablement `root`

### 3. Vérifier que MAMP est démarré

Assurez-vous que :
- ✅ MAMP est démarré
- ✅ Le serveur MySQL est actif (bouton vert dans MAMP)
- ✅ Le port MySQL est accessible

### 4. Tester la connexion

Exécutez le script de test :

```bash
cd c:\MAMP\htdocs\project_douane\sam
python test_connection.py
```

### 5. Si vous utilisez PostgreSQL en local

Si vous utilisez PostgreSQL au lieu de MySQL, modifiez le fichier `.env` :

```env
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=votre_mot_de_passe
DB_NAME=douane_simple
```

Ou utilisez une connection string :

```env
DATABASE_URL=postgresql://user:password@localhost:5432/douane_simple
```

## Différence entre local et production

- **En local** : Le fichier `.env` est utilisé pour charger les variables d'environnement
- **En production** : Les secrets Streamlit (fichier `.streamlit/secrets.toml`) sont utilisés

Le code essaie d'abord d'utiliser les secrets Streamlit, puis tombe sur le fichier `.env` si les secrets ne sont pas disponibles.

## Problèmes courants

### Erreur : "Access denied for user 'root'@'localhost'"

**Solution** : Vérifiez le mot de passe dans le fichier `.env`
- Essayez avec un mot de passe vide : `DB_PASSWORD=`
- Essayez avec `root` : `DB_PASSWORD=root`
- Vérifiez dans les préférences MAMP

### Erreur : "Can't connect to MySQL server"

**Solution** : 
- Vérifiez que MAMP est démarré
- Vérifiez le port dans le fichier `.env` (3306 ou 8889)
- Vérifiez que MySQL est actif dans MAMP

### Erreur : "Unknown database 'douane_simple'"

**Solution** : 
- Créez la base de données dans phpMyAdmin
- Ou modifiez `DB_NAME` dans le fichier `.env` avec le nom de votre base de données

## Fichiers importants

- `.env` : Configuration locale (à la racine du projet)
- `.streamlit/secrets.toml` : Configuration production (non versionné)
- `sam/database.py` : Module de détection automatique MySQL/PostgreSQL
- `sam/database_mysql.py` : Module de connexion MySQL
- `sam/database_postgresql.py` : Module de connexion PostgreSQL

