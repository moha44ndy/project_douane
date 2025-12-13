#!/usr/bin/env python3
"""
Script de migration des données JSON vers MySQL
Migre users.json et table_data.json vers la base de données
"""
import json
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from sam.database import get_db
    from sam.auth_db import hash_password
    USE_DB = True
except ImportError:
    print("❌ Erreur: Impossible d'importer le module database")
    print("Assurez-vous que mysql-connector-python est installé: pip install mysql-connector-python")
    USE_DB = False

def migrate_users():
    """Migre users.json vers la table users"""
    print("📦 Migration des utilisateurs...")
    
    # Charger users.json
    users_file = Path(__file__).parent.parent / "users.json"
    if not users_file.exists():
        print("⚠️  users.json n'existe pas, ignoré")
        return
    
    with open(users_file, 'r', encoding='utf-8') as f:
        users = json.load(f)
    
    if not USE_DB:
        print("❌ Base de données non disponible")
        return
    
    db = get_db()
    if not db.test_connection():
        print("❌ Impossible de se connecter à MySQL")
        return
    
    migrated = 0
    errors = 0
    
    for user in users:
        try:
            # Vérifier si l'utilisateur existe déjà
            check_query = "SELECT user_id FROM users WHERE identifiant_user = %s"
            existing = db.execute_query(check_query, (user.get('identifiant_user'),))
            
            if existing:
                print(f"  ⏭️  Utilisateur {user.get('identifiant_user')} existe déjà, ignoré")
                continue
            
            # Insérer l'utilisateur
            insert_query = """
                INSERT INTO users (user_id, nom_user, identifiant_user, email, password_hash, statut, is_admin, date_creation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            password_hash = user.get('password_hash') or user.get('mot_de_passe')
            if not password_hash:
                # Générer un hash par défaut si manquant
                password_hash = hash_password('changeme123')
            
            params = (
                user.get('user_id'),
                user.get('nom_user'),
                user.get('identifiant_user'),
                user.get('email'),
                password_hash,
                user.get('statut', 'actif'),
                1 if user.get('is_admin') else 0,
                user.get('date_creation', '2025-01-01T00:00:00')
            )
            
            db.execute_insert(insert_query, params)
            migrated += 1
            print(f"  ✅ {user.get('nom_user')} migré")
            
        except Exception as e:
            errors += 1
            print(f"  ❌ Erreur pour {user.get('nom_user')}: {e}")
    
    print(f"\n✅ {migrated} utilisateur(s) migré(s)")
    if errors > 0:
        print(f"⚠️  {errors} erreur(s)")


def migrate_classifications():
    """Migre table_data.json vers la table classifications"""
    print("\n📦 Migration des classifications...")
    
    # Charger table_data.json
    table_file = Path(__file__).parent.parent / "table_data.json"
    if not table_file.exists():
        print("⚠️  table_data.json n'existe pas, ignoré")
        return
    
    with open(table_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        print("⚠️  table_data.json n'est pas une liste, ignoré")
        return
    
    if not USE_DB:
        print("❌ Base de données non disponible")
        return
    
    db = get_db()
    if not db.test_connection():
        print("❌ Impossible de se connecter à MySQL")
        return
    
    # Récupérer le premier utilisateur comme user_id par défaut
    users_query = "SELECT user_id FROM users LIMIT 1"
    users_result = db.execute_query(users_query)
    default_user_id = users_result[0]['user_id'] if users_result else 1
    
    migrated = 0
    errors = 0
    
    for item in data:
        try:
            # Extraire les données selon la structure
            if isinstance(item, dict) and 'product' in item and 'classification' in item:
                product = item.get('product', {})
                classification = item.get('classification', {})
                
                description = product.get('description', '')
                valeur = product.get('value', 'Non renseigné')
                origine = product.get('origin', 'Non renseigné')
                
                code = classification.get('code', '')
                section_obj = classification.get('section', {})
                section = section_obj.get('number') if isinstance(section_obj, dict) else section_obj
                confidence = classification.get('confidence', 0)
                
                # Extraire le chapitre du code
                chapitre = None
                if code:
                    digits = ''.join(c for c in code if c.isdigit())
                    if len(digits) >= 2:
                        chapitre = digits[:2]
                
            else:
                # Format alternatif
                description = item.get('description', '')
                valeur = item.get('value', 'Non renseigné')
                origine = item.get('origin', 'Non renseigné')
                code = item.get('code', '')
                section = item.get('section', '')
                confidence = item.get('confidence', 0)
                chapitre = item.get('chapter', '')
            
            # Insérer dans la base de données
            insert_query = """
                INSERT INTO classifications 
                (user_id, description_produit, valeur_produit, origine_produit, 
                 code_tarifaire, section, chapitre, confidence_score, statut_validation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'en_attente')
            """
            
            params = (
                default_user_id,
                description,
                str(valeur),
                str(origine),
                code if code else None,
                section if section else None,
                chapitre if chapitre else None,
                float(confidence) * 100 if isinstance(confidence, (int, float)) and confidence <= 1 else float(confidence) if confidence else None
            )
            
            db.execute_insert(insert_query, params)
            migrated += 1
            
        except Exception as e:
            errors += 1
            print(f"  ❌ Erreur pour l'item: {e}")
    
    print(f"\n✅ {migrated} classification(s) migrée(s)")
    if errors > 0:
        print(f"⚠️  {errors} erreur(s)")


def main():
    """Fonction principale"""
    print("=" * 60)
    print("Migration JSON → MySQL")
    print("Système de Classification Douanière CEDEAO")
    print("=" * 60)
    print()
    
    if not USE_DB:
        print("❌ Module database non disponible")
        print("Installez: pip install mysql-connector-python")
        return
    
    # Tester la connexion
    db = get_db()
    if not db.test_connection():
        print("❌ Impossible de se connecter à MySQL")
        print("Vérifiez votre configuration dans .env ou Streamlit secrets")
        return
    
    print("✅ Connexion MySQL réussie\n")
    
    # Migrer les utilisateurs
    migrate_users()
    
    # Migrer les classifications
    migrate_classifications()
    
    print("\n" + "=" * 60)
    print("✅ Migration terminée!")
    print("=" * 60)


if __name__ == "__main__":
    main()

