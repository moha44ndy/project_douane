"""
Module de gestion du cache Redis partagé
Système de Classification Douanière CEDEAO
"""
import redis
import json
import hashlib
from typing import Optional, Dict, Any
from pathlib import Path
import os

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

# Variable globale pour le client Redis (initialisée de manière paresseuse)
_redis_client = None
USE_REDIS = True

def get_redis_client():
    """Obtient le client Redis, en le créant si nécessaire"""
    global _redis_client, USE_REDIS
    
    if _redis_client is not None:
        return _redis_client
    
    try:
        # Configuration Redis depuis les variables d'environnement
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_password = os.getenv('REDIS_PASSWORD', None)
        redis_db = int(os.getenv('REDIS_DB', 0))
        
        # Essayer d'abord Streamlit secrets (pour production)
        try:
            import streamlit as st
            if hasattr(st, 'secrets'):
                try:
                    secrets = st.secrets
                    if 'redis' in secrets:
                        redis_host = secrets['redis'].get('host', redis_host)
                        redis_port = int(secrets['redis'].get('port', redis_port))
                        redis_password = secrets['redis'].get('password', redis_password)
                        redis_db = int(secrets['redis'].get('db', redis_db))
                except Exception:
                    pass
        except Exception:
            pass
        
        # Détecter si TLS est nécessaire (Upstash utilise toujours TLS)
        # Si le host contient "upstash.io", activer TLS automatiquement
        use_ssl = 'upstash.io' in redis_host.lower() or 'redislabs.com' in redis_host.lower()
        
        # Créer le client Redis
        _redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            decode_responses=True,  # Décoder automatiquement les réponses en strings
            ssl=use_ssl,  # Activer SSL/TLS pour Upstash et Redis Cloud
            ssl_cert_reqs=None if use_ssl else None,  # Pas de vérification de certificat pour simplifier
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        # Tester la connexion
        _redis_client.ping()
        print("[OK] Connexion Redis etablie")
        USE_REDIS = True
        return _redis_client
        
    except (redis.ConnectionError, redis.TimeoutError, Exception) as e:
        print(f"[ATTENTION] Redis non disponible: {e}")
        print("[ATTENTION] Le cache sera desactive. Pour l'activer, configurez Redis dans .env")
        USE_REDIS = False
        return None


def get_cache_key(query: str) -> str:
    """Génère une clé de cache à partir d'une requête normalisée"""
    # Normaliser la requête : minuscules, supprimer espaces multiples
    normalized = " ".join(query.lower().strip().split())
    # Générer un hash SHA-256
    hash_value = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    # Préfixe pour organiser les clés
    return f"cache:llm:{hash_value}"


def get_from_cache(query: str) -> Optional[str]:
    """
    Récupère une réponse depuis le cache Redis
    Retourne None si la clé n'existe pas ou si Redis n'est pas disponible
    """
    if not USE_REDIS:
        return None
    
    try:
        client = get_redis_client()
        if client is None:
            return None
        
        cache_key = get_cache_key(query)
        cached_value = client.get(cache_key)
        
        if cached_value:
            print("[OK] Reponse recuperee depuis le cache Redis")
            return cached_value
        
        return None
        
    except Exception as e:
        print(f"[ERREUR] Erreur lors de la recuperation du cache Redis: {e}")
        return None


def set_to_cache(query: str, response: str, ttl: int = 604800) -> bool:
    """
    Stocke une réponse dans le cache Redis
    ttl: Time To Live en secondes (par défaut 7 jours = 604800 secondes)
    Retourne True si la mise en cache a réussi, False sinon
    """
    if not USE_REDIS:
        return False
    
    try:
        client = get_redis_client()
        if client is None:
            return False
        
        cache_key = get_cache_key(query)
        # Stocker avec expiration automatique
        client.setex(cache_key, ttl, response)
        print(f"[OK] Reponse mise en cache Redis (TTL: {ttl}s)")
        return True
        
    except Exception as e:
        print(f"[ERREUR] Erreur lors de la mise en cache Redis: {e}")
        return False


def delete_from_cache(query: str) -> bool:
    """
    Supprime une entrée du cache Redis
    Retourne True si la suppression a réussi, False sinon
    """
    if not USE_REDIS:
        return False
    
    try:
        client = get_redis_client()
        if client is None:
            return False
        
        cache_key = get_cache_key(query)
        deleted = client.delete(cache_key)
        
        if deleted:
            print(f"[OK] Entree supprimee du cache Redis")
            return True
        
        return False
        
    except Exception as e:
        print(f"[ERREUR] Erreur lors de la suppression du cache Redis: {e}")
        return False


def clear_cache(pattern: str = "cache:llm:*") -> int:
    """
    Vide le cache Redis selon un pattern
    Retourne le nombre d'entrées supprimées
    """
    if not USE_REDIS:
        return 0
    
    try:
        client = get_redis_client()
        if client is None:
            return 0
        
        # Utiliser SCAN pour trouver toutes les clés correspondant au pattern
        deleted_count = 0
        cursor = 0
        
        while True:
            cursor, keys = client.scan(cursor, match=pattern, count=100)
            if keys:
                deleted_count += client.delete(*keys)
            if cursor == 0:
                break
        
        if deleted_count > 0:
            print(f"[OK] {deleted_count} entree(s) supprimee(s) du cache Redis")
        
        return deleted_count
        
    except Exception as e:
        print(f"[ERREUR] Erreur lors du vidage du cache Redis: {e}")
        return 0


def get_cache_stats() -> Dict[str, Any]:
    """
    Retourne les statistiques du cache Redis
    """
    if not USE_REDIS:
        return {
            "enabled": False,
            "size": 0,
            "status": "Redis non disponible"
        }
    
    try:
        client = get_redis_client()
        if client is None:
            return {
                "enabled": False,
                "size": 0,
                "status": "Redis non connecté"
            }
        
        # Compter les clés du cache
        cursor = 0
        cache_size = 0
        
        while True:
            cursor, keys = client.scan(cursor, match="cache:llm:*", count=100)
            cache_size += len(keys)
            if cursor == 0:
                break
        
        # Obtenir les infos du serveur Redis
        info = client.info('memory')
        memory_used = info.get('used_memory_human', 'N/A')
        
        return {
            "enabled": True,
            "size": cache_size,
            "memory_used": memory_used,
            "status": "Connecté"
        }
        
    except Exception as e:
        return {
            "enabled": False,
            "size": 0,
            "status": f"Erreur: {str(e)}"
        }


def is_redis_available() -> bool:
    """Vérifie si Redis est disponible et fonctionnel"""
    return USE_REDIS and get_redis_client() is not None

