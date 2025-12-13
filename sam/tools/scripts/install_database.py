#!/usr/bin/env python3
"""
Script d'installation de la base de données optimisée
Système de Classification Douanière CEDEAO
"""

import mysql.connector
from mysql.connector import Error
from pathlib import Path
import sys
import getpass

def read_sql_file(file_path):
    """Lit et parse le fichier SQL"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Séparer les commandes SQL (en ignorant les commentaires et les DELIMITER)
        statements = []
        current_statement = ""
        in_delimiter_block = False
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Ignorer les lignes vides et certains commentaires
            if not line or line.startswith('--') or line.startswith('/*'):
                continue
            
            # Gérer les blocs DELIMITER
            if line.startswith('DELIMITER'):
                in_delimiter_block = not in_delimiter_block
                continue
            
            # Si on est dans un bloc DELIMITER, utiliser $$ comme séparateur
            if in_delimiter_block:
                if line.endswith('$$'):
                    current_statement += line.rstrip('$$') + '\n'
                    if current_statement.strip():
                        statements.append(current_statement.strip())
                    current_statement = ""
                else:
                    current_statement += line + '\n'
            else:
                # Sinon, utiliser ; comme séparateur
                if line.endswith(';'):
                    current_statement += line.rstrip(';') + '\n'
                    if current_statement.strip():
                        statements.append(current_statement.strip())
                    current_statement = ""
                else:
                    current_statement += line + '\n'
        
        return statements
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du fichier SQL: {e}")
        return None

def execute_sql_statements(connection, statements):
    """Exécute les commandes SQL"""
    cursor = connection.cursor()
    errors = []
    
    for i, statement in enumerate(statements, 1):
        if not statement.strip():
            continue
        
        try:
            # Exécuter la commande
            for result in cursor.execute(statement, multi=True):
                if result.with_rows:
                    result.fetchall()
            connection.commit()
            print(f"  ✓ Commande {i}/{len(statements)} exécutée")
        except Error as e:
            error_msg = f"Erreur à la commande {i}: {str(e)}"
            errors.append(error_msg)
            print(f"  ⚠ {error_msg}")
            # Continuer malgré l'erreur (certaines commandes peuvent échouer si déjà exécutées)
    
    cursor.close()
    return errors

def install_database():
    """Fonction principale d'installation"""
    print("=" * 50)
    print("Installation de la Base de Données")
    print("Système de Classification Douanière CEDEAO")
    print("=" * 50)
    print()
    
    # Configuration par défaut
    config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'database': None  # Sera créée par le script
    }
    
    # Demander les informations de connexion
    print("Configuration de la connexion MySQL:")
    config['host'] = input(f"Hôte [{config['host']}]: ").strip() or config['host']
    port_input = input(f"Port [{config['port']}]: ").strip()
    if port_input:
        config['port'] = int(port_input)
    config['user'] = input(f"Utilisateur [{config['user']}]: ").strip() or config['user']
    config['password'] = getpass.getpass("Mot de passe: ")
    
    # Chemin du fichier SQL
    script_dir = Path(__file__).parent
    sql_file = script_dir.parent.parent.parent / "douane_optimized.sql"
    
    if not sql_file.exists():
        print(f"❌ Erreur: Le fichier {sql_file} n'existe pas!")
        print("Assurez-vous que le fichier est dans le répertoire racine du projet.")
        return False
    
    print()
    print(f"Fichier SQL: {sql_file}")
    print()
    
    # Lire le fichier SQL
    print("📖 Lecture du fichier SQL...")
    statements = read_sql_file(sql_file)
    
    if not statements:
        print("❌ Aucune commande SQL trouvée!")
        return False
    
    print(f"  ✓ {len(statements)} commandes SQL trouvées")
    print()
    
    # Se connecter à MySQL
    print("🔌 Connexion à MySQL...")
    try:
        # Se connecter sans base de données spécifique
        connection = mysql.connector.connect(
            host=config['host'],
            port=config['port'],
            user=config['user'],
            password=config['password']
        )
        print("  ✓ Connexion réussie")
    except Error as e:
        print(f"  ❌ Erreur de connexion: {e}")
        return False
    
    print()
    print("⏳ Exécution des commandes SQL...")
    print()
    
    # Exécuter les commandes
    errors = execute_sql_statements(connection, statements)
    
    connection.close()
    
    print()
    if errors:
        print(f"⚠ {len(errors)} erreur(s) rencontrée(s) (peut être normal si la base existe déjà)")
        for error in errors[:5]:  # Afficher les 5 premières erreurs
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... et {len(errors) - 5} autre(s) erreur(s)")
    else:
        print("✅ Installation réussie!")
    
    print()
    print("📝 Informations importantes:")
    print("  - Base de données: douane_optimized")
    print("  - Utilisateur admin: admin")
    print("  - Mot de passe admin: admin123 (⚠️ À CHANGER!)")
    print()
    print("📋 Prochaines étapes:")
    print("  1. Changer le mot de passe de l'administrateur")
    print("  2. Configurer les paramètres de connexion dans votre application")
    print("  3. Faire une sauvegarde de la base de données")
    print()
    
    return True

if __name__ == "__main__":
    try:
        success = install_database()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Installation annulée par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erreur inattendue: {e}")
        sys.exit(1)

