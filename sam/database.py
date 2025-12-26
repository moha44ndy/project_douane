"""
Module de connexion à la base de données avec détection automatique MySQL/PostgreSQL
Système de Classification Douanière CEDEAO
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import streamlit as st

# Charger les variables d'environnement depuis .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

# Importer l'exception Streamlit pour les secrets
try:
    from streamlit.errors import StreamlitSecretNotFoundError
except ImportError:
    StreamlitSecretNotFoundError = Exception

def _detect_database_type() -> str:
    """
    Détecte automatiquement le type de base de données à utiliser
    Retourne 'mysql' ou 'postgresql'
    """
    # Vérifier d'abord la variable d'environnement explicite
    db_type = os.getenv('DB_TYPE', '').lower()
    if db_type in ['mysql', 'postgresql', 'postgres']:
        return 'postgresql' if db_type in ['postgresql', 'postgres'] else 'mysql'
    
    # Vérifier les secrets Streamlit
    try:
        if hasattr(st, 'secrets'):
            try:
                secrets = st.secrets
                if 'database' in secrets:
                    # Si connection_string contient postgresql, c'est PostgreSQL
                    if 'connection_string' in secrets['database']:
                        conn_str = secrets['database']['connection_string']
                        if 'postgresql' in conn_str.lower() or 'postgres' in conn_str.lower():
                            return 'postgresql'
                    
                    # Vérifier le port
                    port = secrets['database'].get('port', 3306)
                    if port == 5432:
                        return 'postgresql'
                    elif port == 3306:
                        return 'mysql'
            except (StreamlitSecretNotFoundError, KeyError, AttributeError, TypeError):
                pass
    except (AttributeError, TypeError):
        pass
    
    # Vérifier DATABASE_URL
    database_url = os.getenv('DATABASE_URL', '')
    if database_url:
        if 'postgresql' in database_url.lower() or 'postgres' in database_url.lower():
            return 'postgresql'
        elif 'mysql' in database_url.lower():
            return 'mysql'
    
    # Vérifier le port par défaut
    port = int(os.getenv('DB_PORT', 3306))
    if port == 5432:
        return 'postgresql'
    elif port == 3306:
        return 'mysql'
    
    # Par défaut, MySQL pour la compatibilité locale
    return 'mysql'

# Détecter le type de base de données
_DB_TYPE = _detect_database_type()

# Importer le module approprié
if _DB_TYPE == 'postgresql':
    try:
        from database_postgresql import Database, get_db
        _DB_MODULE = 'postgresql'
    except ImportError:
        # Fallback vers MySQL si PostgreSQL n'est pas disponible
        try:
            from database_mysql import Database, get_db
            _DB_MODULE = 'mysql'
            print("⚠️ PostgreSQL non disponible, utilisation de MySQL")
        except ImportError:
            raise ImportError("Aucun module de base de données disponible (MySQL ou PostgreSQL)")
else:
    try:
        from database_mysql import Database, get_db
        _DB_MODULE = 'mysql'
    except ImportError:
        # Fallback vers PostgreSQL si MySQL n'est pas disponible
        try:
            from database_postgresql import Database, get_db
            _DB_MODULE = 'postgresql'
            print("⚠️ MySQL non disponible, utilisation de PostgreSQL")
        except ImportError:
            raise ImportError("Aucun module de base de données disponible (MySQL ou PostgreSQL)")

# Exporter les fonctions et classes
__all__ = ['Database', 'get_db', '_DB_TYPE', '_DB_MODULE']
