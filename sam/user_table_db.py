"""
Module de gestion de la table utilisateur (produits dans le tableau)
Système de Classification Douanière CEDEAO
"""
import streamlit as st
from typing import Optional, List, Dict, Any
from datetime import datetime

# Essayer d'importer le module database
try:
    from database import get_db, _get_db_type
    USE_DATABASE = True
except ImportError:
    USE_DATABASE = False


def ensure_table_exists():
    """Crée la table user_table_products si elle n'existe pas"""
    if not USE_DATABASE:
        return False
    
    try:
        db = get_db()
        if not db.test_connection():
            return False
        
        is_postgresql = (_get_db_type() == 'postgresql')
        
        # Vérifier si la table existe
        if is_postgresql:
            check_query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'user_table_products'
                )
            """
        else:
            check_query = """
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'user_table_products'
            """
        
        result = db.execute_query(check_query)
        
        if is_postgresql:
            table_exists = result[0].get('exists', False) if result else False
        else:
            table_exists = (result[0].get('count', 0) > 0) if result else False
        
        if not table_exists:
            # Créer la table
            if is_postgresql:
                create_query = """
                    CREATE TABLE user_table_products (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        classification_id INTEGER NOT NULL,
                        display_order INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                        FOREIGN KEY (classification_id) REFERENCES classifications(id) ON DELETE CASCADE,
                        UNIQUE (user_id, classification_id)
                    )
                """
            else:
                create_query = """
                    CREATE TABLE user_table_products (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        classification_id INT NOT NULL,
                        display_order INT DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                        FOREIGN KEY (classification_id) REFERENCES classifications(id) ON DELETE CASCADE,
                        UNIQUE KEY unique_user_classification (user_id, classification_id),
                        INDEX idx_user_id (user_id),
                        INDEX idx_classification_id (classification_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            
            db.execute_update(create_query, ())
            print("DEBUG: Table user_table_products créée avec succès")
            return True
        else:
            print("DEBUG: Table user_table_products existe déjà")
            return True
    except Exception as e:
        print(f"Erreur lors de la création/vérification de la table user_table_products: {e}")
        return False


def add_product_to_table(classification_id: int, user_id: Optional[int] = None) -> bool:
    """Ajoute un produit au tableau de l'utilisateur"""
    if not USE_DATABASE:
        return False
    
    try:
        from classifications_db import get_current_user_id
        if not user_id:
            user_id = get_current_user_id()
        
        if not user_id:
            return False
        
        ensure_table_exists()
        
        db = get_db()
        if not db.test_connection():
            return False
        
        # Vérifier si le produit existe déjà dans le tableau
        check_query = "SELECT id FROM user_table_products WHERE user_id = %s AND classification_id = %s"
        existing = db.execute_query(check_query, (user_id, classification_id))
        
        if existing:
            # Le produit existe déjà, mettre à jour l'ordre d'affichage
            update_query = """
                UPDATE user_table_products 
                SET display_order = (SELECT COALESCE(MAX(display_order), 0) + 1 FROM user_table_products WHERE user_id = %s),
                    created_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND classification_id = %s
            """
            db.execute_update(update_query, (user_id, user_id, classification_id))
        else:
            # Ajouter le produit
            # Récupérer le prochain ordre d'affichage
            order_query = "SELECT COALESCE(MAX(display_order), 0) + 1 as next_order FROM user_table_products WHERE user_id = %s"
            order_result = db.execute_query(order_query, (user_id,))
            next_order = order_result[0].get('next_order', 1) if order_result else 1
            
            insert_query = """
                INSERT INTO user_table_products (user_id, classification_id, display_order)
                VALUES (%s, %s, %s)
            """
            db.execute_insert(insert_query, (user_id, classification_id, next_order))
        
        return True
    except Exception as e:
        print(f"Erreur lors de l'ajout du produit au tableau: {e}")
        return False


def remove_product_from_table(classification_id: int, user_id: Optional[int] = None) -> bool:
    """Retire un produit du tableau de l'utilisateur"""
    if not USE_DATABASE:
        return False
    
    try:
        from classifications_db import get_current_user_id
        if not user_id:
            user_id = get_current_user_id()
        
        if not user_id:
            return False
        
        db = get_db()
        if not db.test_connection():
            return False
        
        delete_query = "DELETE FROM user_table_products WHERE user_id = %s AND classification_id = %s"
        db.execute_update(delete_query, (user_id, classification_id))
        return True
    except Exception as e:
        print(f"Erreur lors de la suppression du produit du tableau: {e}")
        return False


def clear_user_table(user_id: Optional[int] = None) -> bool:
    """Vide le tableau de l'utilisateur"""
    if not USE_DATABASE:
        return False
    
    try:
        from classifications_db import get_current_user_id
        if not user_id:
            user_id = get_current_user_id()
        
        if not user_id:
            return False
        
        db = get_db()
        if not db.test_connection():
            return False
        
        delete_query = "DELETE FROM user_table_products WHERE user_id = %s"
        db.execute_update(delete_query, (user_id,))
        return True
    except Exception as e:
        print(f"Erreur lors du vidage du tableau: {e}")
        return False


def load_user_table_products(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Charge les produits du tableau de l'utilisateur depuis la base de données"""
    if not USE_DATABASE:
        return []
    
    try:
        from classifications_db import get_current_user_id, load_classifications_by_ids
        if not user_id:
            user_id = get_current_user_id()
        
        if not user_id:
            return []
        
        ensure_table_exists()
        
        db = get_db()
        if not db.test_connection():
            return []
        
        # Récupérer les IDs des classifications dans le tableau, triés par ordre d'affichage
        query = """
            SELECT classification_id, display_order
            FROM user_table_products
            WHERE user_id = %s
            ORDER BY display_order ASC, created_at ASC
        """
        result = db.execute_query(query, (user_id,))
        
        if not result:
            return []
        
        # Extraire les IDs
        classification_ids = [row['classification_id'] for row in result]
        
        # Charger les classifications complètes
        classifications = load_classifications_by_ids(classification_ids, user_id)
        
        # Préserver l'ordre d'affichage
        id_to_classification = {cls.get('id'): cls for cls in classifications if cls.get('id')}
        ordered_classifications = []
        for cid in classification_ids:
            if cid in id_to_classification:
                ordered_classifications.append(id_to_classification[cid])
        
        return ordered_classifications
    except Exception as e:
        print(f"Erreur lors du chargement des produits du tableau: {e}")
        return []


def get_user_table_count(user_id: Optional[int] = None) -> int:
    """Retourne le nombre de produits dans le tableau de l'utilisateur"""
    if not USE_DATABASE:
        return 0
    
    try:
        from classifications_db import get_current_user_id
        if not user_id:
            user_id = get_current_user_id()
        
        if not user_id:
            return 0
        
        ensure_table_exists()
        
        db = get_db()
        if not db.test_connection():
            return 0
        
        query = "SELECT COUNT(*) as count FROM user_table_products WHERE user_id = %s"
        result = db.execute_query(query, (user_id,))
        
        if result:
            return int(result[0].get('count', 0))
        return 0
    except Exception as e:
        print(f"Erreur lors du comptage des produits du tableau: {e}")
        return 0

