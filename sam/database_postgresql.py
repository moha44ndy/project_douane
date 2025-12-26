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

# Forcer IPv4 au niveau système si possible
# Note: Cela peut ne pas fonctionner dans tous les environnements
try:
    # Désactiver IPv6 pour les sockets (si supporté)
    socket.AF_INET6 = None  # Ne fonctionnera pas, mais on essaie
except:
    pass

# Variable d'environnement pour forcer IPv4 (si psycopg2 le supporte)
os.environ.setdefault('PGHOSTADDR', '')  # Vide pour forcer la résolution

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
    
    def _resolve_ipv4(self, hostname: str) -> str:
        """Résout un hostname en adresse IPv4 pour éviter les problèmes IPv6"""
        try:
            # Forcer la résolution en IPv4 seulement
            addrinfo = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
            if addrinfo:
                ipv4 = addrinfo[0][4][0]
                print(f"✅ Hostname '{hostname}' résolu en IPv4: {ipv4}")
                return ipv4  # Retourner l'adresse IPv4
            else:
                print(f"⚠️ Aucune adresse IPv4 trouvée pour '{hostname}'")
        except (socket.gaierror, IndexError, OSError) as e:
            print(f"⚠️ Erreur lors de la résolution IPv4 de '{hostname}': {e}")
        return hostname  # Retourner le hostname original si la résolution échoue
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """Retourne les paramètres de connexion au format psycopg2"""
        config = self._config.copy()
        if 'connection_string' in config:
            # Extraire les paramètres de la connection string
            import urllib.parse
            conn_str = config['connection_string']
            parsed = urllib.parse.urlparse(conn_str)
            
            host = parsed.hostname
            # Résoudre en IPv4 pour éviter les problèmes IPv6
            host_ipv4 = self._resolve_ipv4(host) if host else host
            
            return {
                'host': host_ipv4,
                'port': parsed.port or 5432,
                'user': parsed.username,
                'password': urllib.parse.unquote(parsed.password) if parsed.password else '',
                'database': parsed.path.lstrip('/')
            }
        else:
            # Résoudre le hostname en IPv4 si présent
            if 'host' in config:
                config['host'] = self._resolve_ipv4(config['host'])
            return config
    
    def create_connection_pool(self):
        """Crée un pool de connexions"""
        if self._connection_pool is None:
            try:
                params = self._get_connection_params()
                host = params['host']
                
                # Si la résolution IPv4 a échoué et qu'on a toujours un hostname,
                # essayer de construire une connection string avec options IPv4
                if not self._is_ip_address(host) and host == params.get('host'):
                    # Utiliser une connection string avec options pour forcer IPv4
                    import urllib.parse
                    password_encoded = urllib.parse.quote(params['password'])
                    conn_str = f"postgresql://{params['user']}:{password_encoded}@{host}:{params['port']}/{params['database']}"
                    
                    # Essayer avec la connection string directement
                    try:
                        print(f"🔌 Tentative de connexion avec connection string à: {host}:{params['port']}")
                        self._connection_pool = pool.SimpleConnectionPool(1, 5, conn_str)
                        print(f"✅ Pool de connexions créé avec succès (connection string)")
                        return
                    except Exception as e1:
                        print(f"⚠️ Échec avec connection string, essai avec paramètres: {e1}")
                
                # Si c'est un hostname, essayer de résoudre en IPv4
                if not self._is_ip_address(host):
                    resolved_host = self._resolve_ipv4(host)
                    if resolved_host != host:
                        host = resolved_host
                        params['host'] = host
                        print(f"✅ Hostname résolu en IPv4: {host}")
                    else:
                        print(f"⚠️ Résolution IPv4 échouée, utilisation du hostname: {host}")
                
                print(f"🔌 Tentative de connexion à: {host}:{params['port']}")
                
                # Toujours utiliser les paramètres individuels
                pool_params = {
                    'host': host,
                    'port': params['port'],
                    'user': params['user'],
                    'password': params['password'],
                    'database': params['database']
                }
                self._connection_pool = pool.SimpleConnectionPool(1, 5, **pool_params)
                print(f"✅ Pool de connexions créé avec succès")
            except Exception as e:
                print(f"Erreur lors de la création du pool de connexions: {e}")
                raise
    
    def _is_ip_address(self, host: str) -> bool:
        """Vérifie si host est une adresse IP (IPv4)"""
        try:
            socket.inet_aton(host)
            return True
        except socket.error:
            return False
    
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

