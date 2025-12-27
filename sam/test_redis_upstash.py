"""
Script de test pour vérifier la connexion Redis Upstash
Peut être utilisé localement ou sur Streamlit Cloud
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("TEST DE CONNEXION REDIS UPSTASH")
print("=" * 70)

# Test 1: Import du module
print("\n[1] Test d'import du module cache_redis...")
try:
    from cache_redis import (
        get_redis_client,
        is_redis_available,
        get_from_cache,
        set_to_cache,
        delete_from_cache,
        get_cache_stats,
        get_cache_key
    )
    print("[OK] Module cache_redis importe avec succes")
except ImportError as e:
    print(f"[ERREUR] Erreur d'import: {e}")
    sys.exit(1)

# Test 2: Vérifier la configuration
print("\n[2] Verification de la configuration Redis...")
try:
    import os
    from pathlib import Path
    
    # Charger .env si disponible
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
        print("[INFO] Fichier .env charge")
    
    # Vérifier les variables d'environnement
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = os.getenv('REDIS_PORT', 6379)
    redis_password = os.getenv('REDIS_PASSWORD', None)
    
    print(f"   Host: {redis_host}")
    print(f"   Port: {redis_port}")
    print(f"   Password: {'***' if redis_password else 'Non defini'}")
    
    # Vérifier Streamlit secrets si disponible
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'redis' in st.secrets:
            print("[INFO] Configuration Streamlit Secrets detectee")
            secrets = st.secrets['redis']
            print(f"   Host (secrets): {secrets.get('host', 'N/A')}")
            print(f"   Port (secrets): {secrets.get('port', 'N/A')}")
    except:
        print("[INFO] Streamlit non disponible (mode test local)")
        
except Exception as e:
    print(f"[ATTENTION] Erreur lors de la verification: {e}")

# Test 3: Connexion Redis
print("\n[3] Test de connexion a Redis...")
try:
    client = get_redis_client()
    if client is None:
        print("[ERREUR] Client Redis est None")
        print("[INFO] Verifiez votre configuration dans .env ou Streamlit Secrets")
    else:
        # Tester la connexion
        result = client.ping()
        if result:
            print("[OK] Connexion Redis etablie avec succes!")
            print("[OK] Redis Upstash fonctionne correctement")
        else:
            print("[ERREUR] Connexion Redis echouee")
except Exception as e:
    print(f"[ERREUR] Erreur de connexion: {e}")
    print("\n[INFO] Verifications a faire:")
    print("   1. Verifiez que Redis est accessible")
    print("   2. Verifiez le host, port et password")
    print("   3. Pour Upstash, verifiez que TLS est active")
    print("   4. Verifiez votre connexion internet")

# Test 4: Disponibilité
print("\n[4] Verification de la disponibilite Redis...")
available = is_redis_available()
if available:
    print("[OK] Redis est disponible et fonctionnel")
else:
    print("[ATTENTION] Redis n'est pas disponible")
    print("[INFO] Le systeme utilisera le cache local en fallback")

# Test 5: Statistiques
print("\n[5] Statistiques du cache...")
try:
    stats = get_cache_stats()
    print(f"   Statut: {stats.get('status', 'N/A')}")
    print(f"   Active: {stats.get('enabled', False)}")
    print(f"   Taille: {stats.get('size', 0)} entree(s)")
    if 'memory_used' in stats:
        print(f"   Memoire utilisee: {stats.get('memory_used', 'N/A')}")
except Exception as e:
    print(f"[ERREUR] Erreur lors de la recuperation des statistiques: {e}")

# Test 6: Test de mise en cache (si Redis disponible)
if available:
    print("\n[6] Test de mise en cache...")
    test_query = "test-upstash-connection"
    test_response = '{"test": "Connexion Upstash reussie", "timestamp": "2025"}'
    
    try:
        # Mettre en cache
        success = set_to_cache(test_query, test_response, ttl=60)
        if success:
            print(f"[OK] Reponse mise en cache pour: '{test_query}'")
        else:
            print(f"[ERREUR] Echec de la mise en cache")
    except Exception as e:
        print(f"[ERREUR] Erreur lors de la mise en cache: {e}")
    
    # Test 7: Récupération
    print("\n[7] Test de recuperation depuis le cache...")
    try:
        cached_response = get_from_cache(test_query)
        if cached_response:
            print(f"[OK] Reponse recuperee depuis le cache Upstash!")
            print(f"   Longueur: {len(cached_response)} caracteres")
            if cached_response == test_response:
                print("[OK] La reponse correspond exactement")
            else:
                print("[ATTENTION] La reponse ne correspond pas exactement")
        else:
            print("[ERREUR] Aucune reponse trouvee dans le cache")
    except Exception as e:
        print(f"[ERREUR] Erreur lors de la recuperation: {e}")
    
    # Test 8: Nettoyage
    print("\n[8] Nettoyage du test...")
    try:
        deleted = delete_from_cache(test_query)
        if deleted:
            print("[OK] Entree de test supprimee")
    except Exception as e:
        print(f"[ATTENTION] Erreur lors de la suppression: {e}")

# Résumé
print("\n" + "=" * 70)
print("RESUME DU TEST")
print("=" * 70)

if available:
    print("[OK] Cache Redis Upstash: OPERATIONNEL")
    print("[OK] Configuration correcte")
    print("[OK] Pret pour la production sur Streamlit Cloud")
    print("\n[INFO] Prochaines etapes:")
    print("   1. Configurez les secrets dans Streamlit Cloud")
    print("   2. Redepoyez l'application")
    print("   3. Verifiez les logs pour confirmer la connexion")
else:
    print("[ATTENTION] Redis n'est pas disponible")
    print("[INFO] Verifiez votre configuration:")
    print("   - Local: Verifiez .env (REDIS_HOST, REDIS_PORT, REDIS_PASSWORD)")
    print("   - Streamlit Cloud: Verifiez les secrets [redis]")

print("\n" + "=" * 70)

