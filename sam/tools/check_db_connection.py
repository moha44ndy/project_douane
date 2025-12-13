#!/usr/bin/env python3
"""
Script de vérification de la connexion à la base de données
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("Vérification de la Connexion à la Base de Données")
print("=" * 60)
print()

# 1. Vérifier si les fichiers existent
print("1️⃣ Vérification des fichiers...")
files_to_check = [
    ("sam/database.py", "Module de connexion MySQL"),
    ("sam/auth_db.py", "Module d'authentification avec MySQL"),
    ("sam/auth.py", "Module d'authentification JSON (ancien)"),
    ("douane_db.sql", "Script SQL de la base de données"),
]

all_exist = True
for file_path, description in files_to_check:
    path = Path(file_path)
    if path.exists():
        print(f"  ✅ {description}: {file_path}")
    else:
        print(f"  ❌ {description}: {file_path} - MANQUANT")
        all_exist = False

print()

# 2. Vérifier si mysql-connector est installé
print("2️⃣ Vérification des dépendances...")
try:
    import mysql.connector
    print("  ✅ mysql-connector-python est installé")
    mysql_available = True
except ImportError as e:
    print(f"  ❌ mysql-connector-python n'est PAS installé: {e}")
    print("     Installez avec: pip install mysql-connector-python")
    mysql_available = False

print()

# 3. Vérifier les imports dans le code
print("3️⃣ Vérification de l'utilisation dans le code...")
code_files = [
    ("sam/app.py", "Application principale"),
    ("sam/pages/Login.py", "Page de connexion"),
    ("sam/pages/Administration.py", "Page d'administration"),
]

uses_auth_db = False
uses_auth = False

for file_path, description in code_files:
    path = Path(file_path)
    if path.exists():
        content = path.read_text(encoding='utf-8')
        if 'from auth_db import' in content or 'import auth_db' in content:
            print(f"  ✅ {description}: Utilise auth_db (MySQL)")
            uses_auth_db = True
        elif 'from auth import' in content or 'import auth' in content:
            print(f"  ⚠️  {description}: Utilise auth (JSON uniquement)")
            uses_auth = True

print()

# 4. Vérifier la connexion MySQL (si disponible)
print("4️⃣ Test de connexion MySQL...")
if mysql_available:
    try:
        from database import get_db
        db = get_db()
        if db.test_connection():
            print("  ✅ Connexion MySQL réussie!")
            print(f"     Base de données: {db._config.get('database', 'N/A')}")
            print(f"     Hôte: {db._config.get('host', 'N/A')}")
        else:
            print("  ❌ Connexion MySQL échouée")
            print("     Vérifiez votre configuration (.env ou Streamlit secrets)")
    except Exception as e:
        print(f"  ❌ Erreur lors du test: {e}")
        print("     Vérifiez votre configuration")
else:
    print("  ⏭️  Test ignoré (mysql-connector non installé)")

print()

# 5. Résumé
print("=" * 60)
print("📊 RÉSUMÉ")
print("=" * 60)

if not all_exist:
    print("❌ Certains fichiers sont manquants")
elif not mysql_available:
    print("⚠️  MySQL non disponible - Le projet utilise JSON")
    print("   Pour activer MySQL:")
    print("   1. pip install mysql-connector-python")
    print("   2. Configurer .env avec les paramètres MySQL")
    print("   3. Remplacer 'from auth import' par 'from auth_db import'")
elif uses_auth and not uses_auth_db:
    print("⚠️  Le projet utilise encore auth.py (JSON)")
    print("   Pour activer MySQL:")
    print("   1. Remplacer 'from auth import' par 'from auth_db import'")
    print("   2. Dans: app.py, pages/Login.py, pages/Administration.py")
elif uses_auth_db:
    print("✅ Le projet est configuré pour utiliser MySQL")
    print("   (avec fallback vers JSON si MySQL n'est pas disponible)")
else:
    print("❓ État indéterminé")

print()

