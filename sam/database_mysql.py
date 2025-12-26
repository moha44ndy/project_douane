"""
Module de connexion à la base de données MySQL
Système de Classification Douanière CEDEAO
"""
import mysql.connector
from mysql.connector import Error, pooling
import os
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
import streamlit as st

# Importer l'exception Streamlit pour les secrets
try:
    from streamlit.errors import StreamlitSecretNotFoundError
except ImportError:
    # Pour les versions plus anciennes de Streamlit
    StreamlitSecretNotFoundError = Exception

# Charger les variables d'environnement depuis .env
try:
    from dotenv import load_dotenv
    # Charger depuis la racine du projet
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()  # Essayer le .env par défaut
except ImportError:
    pass  # python-dotenv non installé, utiliser les variables d'environnement système

class Database:
    """Classe singleton pour gérer la connexion à la base de données"""
    
    _instance = None
    _connection_pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self._config = self._get_config()
    
    def _get_config(self) -> Dict[str, Any]:
        """Récupère la configuration depuis les variables d'environnement ou Streamlit secrets"""
        # Essayer d'abord Streamlit secrets (pour production)
        try:
            if hasattr(st, 'secrets'):
                try:
                    # Tenter d'accéder aux secrets (peut lever StreamlitSecretNotFoundError)
                    secrets = st.secrets
                    if 'database' in secrets:
                        # Si connection_string est fournie, on ne peut pas l'utiliser avec MySQL
                        # MySQL nécessite les paramètres individuels
                        if 'connection_string' in secrets['database']:
                            # Pour MySQL, on ne peut pas utiliser connection_string directement
                            # Il faut utiliser les paramètres individuels
                            pass
                        else:
                            return {
                                'host': secrets['database']['host'],
                                'port': secrets['database'].get('port', 3306),
                                'user': secrets['database']['user'],
                                'password': secrets['database']['password'],
                                'database': secrets['database']['database']
                            }
                except StreamlitSecretNotFoundError:
                    # Fichier secrets.toml non trouvé, utiliser .env
                    pass
                except (KeyError, AttributeError, TypeError):
                    # Erreur lors de l'accès aux secrets, utiliser .env
                    pass
        except (AttributeError, TypeError):
            # Streamlit n'est pas disponible ou erreur d'accès, utiliser .env
            pass
        
        # Sinon, utiliser les variables d'environnement
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'douane_simple')
        }
    
    def create_connection_pool(self):
        """Crée un pool de connexions"""
        if self._connection_pool is None:
            try:
                pool_config = {
                    'pool_name': 'douane_pool',
                    'pool_size': 5,
                    'pool_reset_session': True,
                    **self._config
                }
                self._connection_pool = pooling.MySQLConnectionPool(**pool_config)
            except Error as e:
                print(f"Erreur lors de la création du pool de connexions: {e}")
                raise
    
    @contextmanager
    def get_connection(self):
        """Context manager pour obtenir une connexion depuis le pool"""
        connection = None
        try:
            if self._connection_pool is None:
                self.create_connection_pool()
            
            connection = self._connection_pool.get_connection()
            yield connection
        except Error as e:
            print(f"Erreur de connexion à la base de données: {e}")
            # En cas d'erreur, essayer une connexion directe
            try:
                connection = mysql.connector.connect(**self._config)
                yield connection
            except Error as e2:
                print(f"Erreur de connexion directe: {e2}")
                raise
        finally:
            if connection and connection.is_connected():
                connection.close()
    
    def test_connection(self) -> bool:
        """Teste la connexion à la base de données"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                return True
        except Error as e:
            print(f"Erreur de test de connexion: {e}")
            return False
    
    def execute_query(self, query: str, params: Optional[tuple] = None, fetch: bool = True) -> Optional[List[Dict[str, Any]]]:
        """Exécute une requête SELECT et retourne les résultats"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, params or ())
                
                if fetch:
                    results = cursor.fetchall()
                    cursor.close()
                    return results
                else:
                    conn.commit()
                    cursor.close()
                    return None
        except Error as e:
            print(f"Erreur lors de l'exécution de la requête: {e}")
            raise
    
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """Exécute une requête INSERT/UPDATE/DELETE et retourne le nombre de lignes affectées"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, params or ())
                    conn.commit()
                    affected_rows = cursor.rowcount
                    return affected_rows
                except Error as e:
                    conn.rollback()
                    raise
                finally:
                    cursor.close()
        except Error as e:
            print(f"Erreur lors de l'exécution de la mise à jour: {e}")
            raise
    
    def execute_insert(self, query: str, params: Optional[tuple] = None) -> int:
        """Exécute une requête INSERT et retourne l'ID de la dernière ligne insérée"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, params or ())
                    conn.commit()
                    last_id = cursor.lastrowid
                    return last_id
                except Error as e:
                    conn.rollback()
                    raise
                finally:
                    cursor.close()
        except Error as e:
            print(f"Erreur lors de l'insertion: {e}")
            raise

# Instance globale
db = Database()

def get_db() -> Database:
    """Retourne l'instance de la base de données"""
    return db

