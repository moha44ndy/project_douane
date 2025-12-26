"""
Script de diagnostic pour la connexion à la base de données en production
À exécuter dans Streamlit Cloud pour comprendre les problèmes de connexion
"""
import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("DIAGNOSTIC CONNEXION BASE DE DONNÉES - PRODUCTION")
print("=" * 80)

# 1. Vérifier les imports
print("\n1. Vérification des imports...")
try:
    import streamlit as st
    print("   ✅ streamlit importé")
except ImportError as e:
    print(f"   ❌ Erreur import streamlit: {e}")

try:
    import psycopg2
    print(f"   ✅ psycopg2 importé (version: {psycopg2.__version__})")
except ImportError as e:
    print(f"   ❌ Erreur import psycopg2: {e}")

try:
    import socket
    print("   ✅ socket importé")
except ImportError as e:
    print(f"   ❌ Erreur import socket: {e}")

# 2. Vérifier les secrets Streamlit
print("\n2. Vérification des secrets Streamlit...")
try:
    if hasattr(st, 'secrets'):
        secrets = st.secrets
        print("   ✅ st.secrets disponible")
        
        if 'database' in secrets:
            db_secrets = secrets['database']
            print("   ✅ Section [database] trouvée dans les secrets")
            
            # Afficher la configuration (masquer le mot de passe)
            if 'connection_string' in db_secrets:
                conn_str = db_secrets['connection_string']
                # Masquer le mot de passe
                if '@' in conn_str:
                    parts = conn_str.split('@')
                    if ':' in parts[0]:
                        user_pass = parts[0].split(':')
                        if len(user_pass) >= 2:
                            masked = f"{user_pass[0]}:***@{parts[1]}"
                        else:
                            masked = conn_str
                    else:
                        masked = conn_str
                else:
                    masked = conn_str
                print(f"   📋 connection_string: {masked}")
            else:
                print("   📋 Paramètres individuels:")
                print(f"      host: {db_secrets.get('host', 'NON DÉFINI')}")
                print(f"      port: {db_secrets.get('port', 'NON DÉFINI')}")
                print(f"      user: {db_secrets.get('user', 'NON DÉFINI')}")
                print(f"      password: {'***' if db_secrets.get('password') else 'NON DÉFINI'}")
                print(f"      database: {db_secrets.get('database', 'NON DÉFINI')}")
        else:
            print("   ❌ Section [database] NON TROUVÉE dans les secrets")
            print("   ⚠️  Configurez les secrets dans Streamlit Cloud → Settings → Secrets")
    else:
        print("   ❌ st.secrets non disponible")
except Exception as e:
    print(f"   ❌ Erreur lors de l'accès aux secrets: {e}")
    import traceback
    traceback.print_exc()

# 3. Vérifier la détection du type de DB
print("\n3. Vérification de la détection du type de DB...")
try:
    from database import _get_db_type, _get_db_module
    db_type = _get_db_type()
    db_module = _get_db_module()
    print(f"   📋 Type détecté: {db_type}")
    print(f"   📋 Module utilisé: {db_module}")
except Exception as e:
    print(f"   ❌ Erreur lors de la détection: {e}")
    import traceback
    traceback.print_exc()

# 4. Vérifier la résolution DNS
print("\n4. Vérification de la résolution DNS...")
try:
    if hasattr(st, 'secrets') and 'database' in st.secrets:
        db_secrets = st.secrets['database']
        hostname = None
        
        if 'connection_string' in db_secrets:
            import urllib.parse
            parsed = urllib.parse.urlparse(db_secrets['connection_string'])
            hostname = parsed.hostname
        elif 'host' in db_secrets:
            hostname = db_secrets['host']
        
        if hostname:
            print(f"   📋 Hostname: {hostname}")
            
            # Résolution IPv4
            try:
                addrinfo_ipv4 = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
                if addrinfo_ipv4:
                    ipv4 = addrinfo_ipv4[0][4][0]
                    print(f"   ✅ IPv4 résolu: {ipv4}")
                else:
                    print("   ⚠️  Aucune adresse IPv4 trouvée")
            except Exception as e:
                print(f"   ❌ Erreur résolution IPv4: {e}")
            
            # Résolution IPv6
            try:
                addrinfo_ipv6 = socket.getaddrinfo(hostname, None, socket.AF_INET6, socket.SOCK_STREAM)
                if addrinfo_ipv6:
                    ipv6 = addrinfo_ipv6[0][4][0]
                    print(f"   ⚠️  IPv6 résolu: {ipv6}")
                    print("   ⚠️  ATTENTION: IPv6 détecté, cela peut causer des problèmes!")
                else:
                    print("   ✅ Aucune adresse IPv6 trouvée")
            except Exception as e:
                print(f"   ℹ️  Pas d'IPv6 (normal): {e}")
        else:
            print("   ⚠️  Hostname non trouvé dans la configuration")
except Exception as e:
    print(f"   ❌ Erreur lors de la vérification DNS: {e}")
    import traceback
    traceback.print_exc()

# 5. Tester la connexion
print("\n5. Test de connexion à la base de données...")
try:
    from database import get_db
    db = get_db()
    print(f"   📋 Type de DB: {type(db).__name__}")
    
    # Vérifier la configuration interne
    if hasattr(db, '_config'):
        config = db._config
        print(f"   📋 Configuration interne:")
        if 'connection_string' in config:
            print(f"      connection_string: {'PRÉSENTE' if config['connection_string'] else 'ABSENTE'}")
        else:
            print(f"      host: {config.get('host', 'N/A')}")
            print(f"      port: {config.get('port', 'N/A')}")
            print(f"      user: {config.get('user', 'N/A')}")
            print(f"      database: {config.get('database', 'N/A')}")
    
    # Tester la connexion
    print("\n   🔌 Tentative de connexion...")
    if db.test_connection():
        print("   ✅ CONNEXION RÉUSSIE!")
        
        # Tester une requête simple
        try:
            result = db.execute_query("SELECT version();")
            if result:
                version = result[0].get('version', 'N/A')
                print(f"   ✅ Requête test réussie")
                print(f"   📋 Version DB: {version[:100]}...")
        except Exception as e:
            print(f"   ⚠️  Erreur lors de la requête test: {e}")
    else:
        print("   ❌ ÉCHEC DE LA CONNEXION")
        
except Exception as e:
    print(f"   ❌ Erreur lors du test de connexion: {e}")
    import traceback
    print("\n   📋 Détails de l'erreur:")
    traceback.print_exc()

# 6. Vérifier les variables d'environnement
print("\n6. Vérification des variables d'environnement...")
env_vars = ['DATABASE_URL', 'DB_HOST', 'DB_PORT', 'DB_USER', 'DB_NAME', 'DB_TYPE']
for var in env_vars:
    value = os.getenv(var)
    if value:
        if 'PASSWORD' in var or 'PASS' in var:
            print(f"   📋 {var}: {'***' if value else 'NON DÉFINI'}")
        else:
            print(f"   📋 {var}: {value}")
    else:
        print(f"   ℹ️  {var}: non défini")

# 7. Informations système
print("\n7. Informations système...")
try:
    import platform
    print(f"   📋 OS: {platform.system()} {platform.release()}")
    print(f"   📋 Python: {sys.version.split()[0]}")
    print(f"   📋 Architecture: {platform.machine()}")
except Exception as e:
    print(f"   ⚠️  Erreur: {e}")

print("\n" + "=" * 80)
print("FIN DU DIAGNOSTIC")
print("=" * 80)

