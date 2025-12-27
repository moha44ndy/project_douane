#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test de connexion à la base de données
"""
import sys
import os
from pathlib import Path

# Forcer l'encodage UTF-8 pour la sortie
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

# Charger les variables d'environnement
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"[OK] Fichier .env charge depuis: {env_path}")
else:
    load_dotenv()
    print("[WARNING] Fichier .env non trouve, utilisation des variables systeme")

# Afficher les variables d'environnement
print("\nVariables d'environnement:")
print(f"  DB_TYPE: {os.getenv('DB_TYPE', 'Non defini')}")
print(f"  DB_HOST: {os.getenv('DB_HOST', 'Non defini')}")
print(f"  DB_PORT: {os.getenv('DB_PORT', 'Non defini')}")
print(f"  DB_USER: {os.getenv('DB_USER', 'Non defini')}")
print(f"  DB_NAME: {os.getenv('DB_NAME', 'Non defini')}")
print(f"  DB_PASSWORD: {'***' if os.getenv('DB_PASSWORD') else 'Non defini'}")

# Tester la connexion
print("\nTest de connexion...")
try:
    from database import get_db
    db = get_db()
    
    # Afficher le type de DB détecté
    try:
        from database import _get_db_type
        db_type = _get_db_type()
        print(f"  Type de DB detecte: {db_type}")
    except:
        pass
    
    # Tester la connexion
    result = db.test_connection()
    if result:
        print("  [OK] Connexion reussie!")
        print(f"  Configuration:")
        if hasattr(db, '_config'):
            config = db._config
            print(f"     Host: {config.get('host', 'N/A')}")
            print(f"     Port: {config.get('port', 'N/A')}")
            print(f"     User: {config.get('user', 'N/A')}")
            print(f"     Database: {config.get('database', 'N/A')}")
    else:
        print("  [ERREUR] Connexion echouee")
        print("  Verifiez:")
        print("     - Que MAMP est demarre")
        print("     - Les parametres dans le fichier .env")
        print("     - Que la base de donnees existe")
except Exception as e:
    print(f"  [ERREUR] {e}")
    import traceback
    traceback.print_exc()

