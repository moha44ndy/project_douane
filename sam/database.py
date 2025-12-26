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
                    # Ports PostgreSQL : 5432 (standard)
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
    # Ports PostgreSQL : 5432 (standard)
    if port == 5432:
        return 'postgresql'
    elif port == 3306:
        return 'mysql'
    
    # Par défaut, MySQL pour la compatibilité locale
    return 'mysql'

# Variables globales pour le type de DB (initialisées paresseusement)
_DB_TYPE = None
_DB_MODULE = None
_Database = None
_get_db_func = None
_initialized = False

def _initialize_db_module():
    """Initialise le module de base de données de manière paresseuse"""
    global _DB_TYPE, _DB_MODULE, _Database, _get_db_func, _initialized
    
    if _initialized:
        return  # Déjà initialisé
    
    # Détecter le type de base de données
    _DB_TYPE = _detect_database_type()
    
    # Importer le module approprié (essayer d'abord les imports relatifs, puis absolus)
    import sys
    from pathlib import Path
    
    # Ajouter le répertoire parent au path si nécessaire
    parent_dir = str(Path(__file__).parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    if _DB_TYPE == 'postgresql':
        try:
            from database_postgresql import Database, get_db
            _Database = Database
            _get_db_func = get_db
            _DB_MODULE = 'postgresql'
        except ImportError:
            # Fallback vers MySQL si PostgreSQL n'est pas disponible
            try:
                from database_mysql import Database, get_db
                _Database = Database
                _get_db_func = get_db
                _DB_MODULE = 'mysql'
            except ImportError:
                raise ImportError("Aucun module de base de donnees disponible (MySQL ou PostgreSQL)")
    else:
        try:
            from database_mysql import Database, get_db
            _Database = Database
            _get_db_func = get_db
            _DB_MODULE = 'mysql'
        except ImportError:
            # Fallback vers PostgreSQL si MySQL n'est pas disponible
            try:
                from database_postgresql import Database, get_db
                _Database = Database
                _get_db_func = get_db
                _DB_MODULE = 'postgresql'
            except ImportError:
                raise ImportError("Aucun module de base de donnees disponible (MySQL ou PostgreSQL)")
    
    _initialized = True

def get_db():
    """Retourne l'instance de la base de données (initialisation paresseuse)"""
    _initialize_db_module()
    return _get_db_func()

def Database():
    """Retourne la classe Database (initialisation paresseuse)"""
    _initialize_db_module()
    return _Database

# Fonction pour obtenir le type de DB (initialisation paresseuse)
def _get_db_type():
    """Retourne le type de base de données détecté"""
    _initialize_db_module()
    return _DB_TYPE

def _get_db_module():
    """Retourne le module de base de données utilisé"""
    _initialize_db_module()
    return _DB_MODULE

# Exporter les fonctions et classes
# _DB_TYPE sera initialisé au premier appel de get_db() ou _get_db_type()
__all__ = ['Database', 'get_db', '_get_db_type', '_get_db_module']
