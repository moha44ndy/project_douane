"""
Module de connexion à la base de données PostgreSQL (Supabase)
Système de Classification Douanière CEDEAO
"""
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
import os
import socket
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
    """Classe singleton pour gérer la connexion à la base de données PostgreSQL"""
    
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
                        # Pour Supabase, utiliser la connection string ou les paramètres individuels
                        if 'connection_string' in secrets['database']:
                            return {'connection_string': secrets['database']['connection_string']}
                        else:
                            return {
                                'host': secrets['database']['host'],
                                'port': secrets['database'].get('port', 5432),
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
        # Supabase fournit souvent une DATABASE_URL
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            return {'connection_string': database_url}
        
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'postgres')
        }
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """Retourne les paramètres de connexion au format psycopg2"""
        config = self._config.copy()
        if 'connection_string' in config:
            # Extraire les paramètres de la connection string si nécessaire
            # ou utiliser directement psycopg2.connect avec la string
            return config
        return config
    
    def create_connection_pool(self):
        """Crée un pool de connexions"""
        if self._connection_pool is None:
            try:
                params = self._get_connection_params()
                # Toujours utiliser les paramètres individuels pour forcer IPv4
                # Supprimer connect_timeout du dict car SimpleConnectionPool ne l'accepte pas directement
                pool_params = {
                    'host': params['host'],
                    'port': params['port'],
                    'user': params['user'],
                    'password': params['password'],
                    'database': params['database']
                }
                self._connection_pool = pool.SimpleConnectionPool(1, 5, **pool_params)
            except Exception as e:
                print(f"Erreur lors de la création du pool de connexions: {e}")
                raise
    
    @contextmanager
    def get_connection(self):
        """Context manager pour obtenir une connexion depuis le pool"""
        connection = None
        try:
            if self._connection_pool is None:
                self.create_connection_pool()
            
            connection = self._connection_pool.getconn()
            yield connection
        except Exception as e:
            print(f"Erreur de connexion à la base de données: {e}")
            # En cas d'erreur, essayer une connexion directe avec IPv4 forcé
            try:
                import socket
                params = self._get_connection_params()
                # Forcer IPv4 en résolvant le hostname en IPv4
                host = params['host']
                try:
                    # Résoudre en IPv4 seulement
                    ipv4 = socket.getaddrinfo(host, params['port'], socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
                    params['host'] = ipv4
                except (socket.gaierror, IndexError):
                    pass  # Utiliser le hostname original si la résolution échoue
                
                # Supprimer connect_timeout du dict pour psycopg2.connect
                connect_params = {k: v for k, v in params.items() if k != 'connect_timeout'}
                connection = psycopg2.connect(**connect_params)
                yield connection
            except Exception as e2:
                print(f"Erreur de connexion directe: {e2}")
                raise
        finally:
            if connection:
                if self._connection_pool:
                    self._connection_pool.putconn(connection)
                else:
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
        except Exception as e:
            print(f"Erreur de test de connexion: {e}")
            return False
    
    def execute_query(self, query: str, params: Optional[tuple] = None, fetch: bool = True) -> Optional[List[Dict[str, Any]]]:
        """Exécute une requête SELECT et retourne les résultats"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(query, params or ())
                
                if fetch:
                    results = cursor.fetchall()
                    cursor.close()
                    # Convertir RealDictRow en dict
                    return [dict(row) for row in results]
                else:
                    conn.commit()
                    cursor.close()
                    return None
        except Exception as e:
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
                except Exception as e:
                    conn.rollback()
                    raise
                finally:
                    cursor.close()
        except Exception as e:
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
                    # Pour PostgreSQL, utiliser RETURNING id dans la requête
                    if 'RETURNING' in query.upper():
                        result = cursor.fetchone()
                        last_id = result[0] if result else None
                    else:
                        # Si pas de RETURNING, récupérer depuis la séquence
                        # Nécessite de connaître le nom de la table et de la colonne
                        # Pour l'instant, retourner None si pas de RETURNING
                        last_id = None
                    return last_id
                except Exception as e:
                    conn.rollback()
                    raise
                finally:
                    cursor.close()
        except Exception as e:
            print(f"Erreur lors de l'insertion: {e}")
            raise

# Instance globale
db = Database()

def get_db() -> Database:
    """Retourne l'instance de la base de données"""
    return db

