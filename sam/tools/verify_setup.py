"""
Script de vérification complète de la configuration
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("VERIFICATION COMPLETE DE LA CONFIGURATION")
print("=" * 60)

# 1. Vérifier les imports
print("\n1. Verification des imports...")
try:
    from database import get_db, Database, _DB_TYPE, _DB_MODULE
    print(f"   OK: Module database importe")
    print(f"   Type detecte: {_DB_TYPE}")
    print(f"   Module utilise: {_DB_MODULE}")
except Exception as e:
    print(f"   ERREUR: {e}")
    sys.exit(1)

# 2. Vérifier les modules spécifiques
print("\n2. Verification des modules specifiques...")
if _DB_TYPE == 'mysql':
    try:
        import database_mysql
        print("   OK: database_mysql disponible")
    except Exception as e:
        print(f"   ERREUR database_mysql: {e}")
else:
    try:
        import database_postgresql
        print("   OK: database_postgresql disponible")
    except Exception as e:
        print(f"   ERREUR database_postgresql: {e}")

# 3. Vérifier les dépendances
print("\n3. Verification des dependances...")
try:
    if _DB_TYPE == 'mysql':
        import mysql.connector
        print("   OK: mysql-connector-python installe")
    else:
        import psycopg2
        print("   OK: psycopg2-binary installe")
except ImportError as e:
    print(f"   ERREUR: {e}")
    print(f"   Installez avec: pip install {'mysql-connector-python' if _DB_TYPE == 'mysql' else 'psycopg2-binary'}")

# 4. Vérifier la configuration
print("\n4. Verification de la configuration...")
try:
    db = get_db()
    print(f"   Type de DB: {type(db).__name__}")
    
    if hasattr(db, '_config'):
        config = db._config
        if 'connection_string' in config:
            # Masquer le mot de passe
            conn_str = config['connection_string']
            if '@' in conn_str:
                parts = conn_str.split('@')
                if ':' in parts[0]:
                    user_pass = parts[0].split(':')
                    if len(user_pass) >= 3:
                        masked = f"{user_pass[0]}:{user_pass[1]}:***@{parts[1]}"
                    else:
                        masked = f"{parts[0].split(':')[0]}:***@{parts[1]}"
                else:
                    masked = conn_str
            else:
                masked = conn_str
            print(f"   Connection string: {masked}")
        else:
            print(f"   Host: {config.get('host', 'N/A')}")
            print(f"   Port: {config.get('port', 'N/A')}")
            print(f"   User: {config.get('user', 'N/A')}")
            print(f"   Database: {config.get('database', 'N/A')}")
except Exception as e:
    print(f"   ERREUR: {e}")

# 5. Tester la connexion
print("\n5. Test de connexion...")
try:
    db = get_db()
    if db.test_connection():
        print("   OK: Connexion reussie!")
        
        # Tester une requête
        try:
            if _DB_TYPE == 'postgresql':
                result = db.execute_query("SELECT version();")
                if result:
                    print(f"   PostgreSQL: {result[0].get('version', 'N/A')[:50]}...")
            else:
                result = db.execute_query("SELECT VERSION();")
                if result:
                    print(f"   MySQL: {result[0].get('VERSION()', 'N/A')[:50]}...")
        except Exception as e:
            print(f"   ATTENTION: Erreur sur requete: {e}")
    else:
        print("   ERREUR: Echec de la connexion")
except Exception as e:
    print(f"   ERREUR: {e}")
    import traceback
    traceback.print_exc()

# 6. Vérifier les modules de feedback
print("\n6. Verification des modules de feedback...")
try:
    from feedback_db import USE_DATABASE
    from database import _get_db_type
    print(f"   USE_DATABASE: {USE_DATABASE}")
    is_postgresql = _get_db_type() == 'postgresql' if USE_DATABASE else False
    print(f"   IS_POSTGRESQL: {is_postgresql}")
    if USE_DATABASE:
        print("   OK: Module feedback_db fonctionnel")
    else:
        print("   ATTENTION: Base de donnees non disponible pour feedback")
except Exception as e:
    print(f"   ERREUR: {e}")

# 7. Vérifier classifications_db
print("\n7. Verification classifications_db...")
try:
    from classifications_db import USE_DATABASE as CLASS_USE_DB
    print(f"   USE_DATABASE: {CLASS_USE_DB}")
    if CLASS_USE_DB:
        print("   OK: Module classifications_db fonctionnel")
except Exception as e:
    print(f"   ERREUR: {e}")

print("\n" + "=" * 60)
print("VERIFICATION TERMINEE")
print("=" * 60)

