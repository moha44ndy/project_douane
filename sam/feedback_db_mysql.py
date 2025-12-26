"""
Module de gestion des feedbacks utilisateurs
Système de Classification Douanière CEDEAO
"""
import streamlit as st
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import hashlib

# Essayer d'importer le module database
try:
    from database import get_db
    USE_DATABASE = True
except ImportError:
    USE_DATABASE = False


def create_feedback_columns():
    """Ajoute les colonnes de feedback à la table classifications si elles n'existent pas"""
    if not USE_DATABASE:
        return False
    
    try:
        db = get_db()
        if not db.test_connection():
            return False
        
        # Vérifier si les colonnes existent déjà
        check_query = """
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'classifications' 
        AND COLUMN_NAME IN ('user_query', 'user_query_hash', 'feedback_rating')
        """
        existing_columns = db.execute_query(check_query, ())
        existing_names = [row.get('COLUMN_NAME', '') for row in existing_columns] if existing_columns else []
        
        # Ajouter les colonnes manquantes
        if 'user_query' not in existing_names:
            db.execute_update("""
                ALTER TABLE classifications 
                ADD COLUMN user_query TEXT NULL COMMENT 'Requête originale de l''utilisateur'
            """, ())
        
        if 'user_query_hash' not in existing_names:
            db.execute_update("""
                ALTER TABLE classifications 
                ADD COLUMN user_query_hash VARCHAR(64) NULL COMMENT 'Hash de la requête pour recherche rapide'
            """, ())
            # Ajouter l'index séparément
            try:
                db.execute_update("""
                    ALTER TABLE classifications 
                    ADD INDEX idx_query_hash (user_query_hash)
                """, ())
            except Exception:
                # L'index existe peut-être déjà, ignorer l'erreur
                pass
        
        if 'feedback_rating' not in existing_names:
            db.execute_update("""
                ALTER TABLE classifications 
                ADD COLUMN feedback_rating ENUM('up', 'down') NULL COMMENT 'Note utilisateur: up (👍) ou down (👎)'
            """, ())
            # Ajouter l'index séparément
            try:
                db.execute_update("""
                    ALTER TABLE classifications 
                    ADD INDEX idx_feedback_rating (feedback_rating)
                """, ())
            except Exception:
                # L'index existe peut-être déjà, ignorer l'erreur
                pass
        
        return True
    except Exception as e:
        print(f"Erreur lors de l'ajout des colonnes de feedback: {e}")
        return False


def get_query_hash(query: str) -> str:
    """Génère un hash pour une requête (normalisé)"""
    # Normaliser la requête : minuscules, supprimer espaces multiples
    normalized = " ".join(query.lower().strip().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def save_feedback(
    user_query: str,
    classification_ids: List[int],
    rating: str,
    user_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Sauvegarde un feedback dans la table classifications
    classification_ids: Liste des IDs de classifications concernées par ce feedback
    """
    if not USE_DATABASE:
        return False, "Base de données non disponible"
    
    if rating not in ['up', 'down']:
        return False, "Rating invalide (doit être 'up' ou 'down')"
    
    if not classification_ids:
        return False, "Aucune classification à noter"
    
    try:
        from auth_db import get_current_user_id
        
        if not user_id:
            user_id = get_current_user_id()
            if not user_id:
                return False, "Utilisateur non identifié"
        
        # Créer les colonnes si elles n'existent pas
        create_feedback_columns()
        
        db = get_db()
        if not db.test_connection():
            return False, "Impossible de se connecter à la base de données"
        
        query_hash = get_query_hash(user_query)
        
        # Mettre à jour toutes les classifications concernées
        update_query = """
        UPDATE classifications 
        SET user_query = %s,
            user_query_hash = %s,
            feedback_rating = %s
        WHERE id IN ({}) AND user_id = %s
        """.format(','.join(['%s'] * len(classification_ids)))
        
        params = [user_query, query_hash, rating] + classification_ids + [user_id]
        db.execute_update(update_query, tuple(params))
        
        return True, f"Feedback enregistré sur {len(classification_ids)} classification(s)"
    
    except Exception as e:
        return False, f"Erreur lors de la sauvegarde du feedback: {str(e)}"


def remove_feedback(
    classification_ids: List[int],
    user_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Retire un feedback (met feedback_rating à NULL)
    classification_ids: Liste des IDs de classifications concernées
    """
    if not USE_DATABASE:
        return False, "Base de données non disponible"
    
    if not classification_ids:
        return False, "Aucune classification spécifiée"
    
    try:
        from auth_db import get_current_user_id
        
        if not user_id:
            user_id = get_current_user_id()
            if not user_id:
                return False, "Utilisateur non identifié"
        
        db = get_db()
        if not db.test_connection():
            return False, "Impossible de se connecter à la base de données"
        
        # Mettre à jour toutes les classifications concernées pour retirer le feedback
        update_query = """
        UPDATE classifications 
        SET feedback_rating = NULL
        WHERE id IN ({}) AND user_id = %s
        """.format(','.join(['%s'] * len(classification_ids)))
        
        params = classification_ids + [user_id]
        db.execute_update(update_query, tuple(params))
        
        return True, f"Feedback retiré sur {len(classification_ids)} classification(s)"
    
    except Exception as e:
        return False, f"Erreur lors du retrait du feedback: {str(e)}"


def check_similar_negative_feedbacks(query: str, similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
    """
    Vérifie s'il existe des feedbacks négatifs pour des requêtes similaires
    Retourne une liste de feedbacks négatifs similaires
    """
    if not USE_DATABASE:
        return []
    
    try:
        db = get_db()
        if not db.test_connection():
            return []
        
        # Récupérer tous les feedbacks négatifs récents depuis classifications
        query_feedback = """
        SELECT user_query, date_classification as created_at, COUNT(*) as count
        FROM classifications
        WHERE feedback_rating = 'down'
        AND user_query IS NOT NULL
        AND date_classification >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY user_query_hash
        ORDER BY date_classification DESC
        LIMIT 50
        """
        
        results = db.execute_query(query_feedback, ())
        
        if not results:
            return []
        
        # Calculer la similarité simple (basée sur les mots communs)
        query_words = set(query.lower().split())
        similar_feedbacks = []
        
        for row in results:
            feedback_query = row.get('user_query', '')
            if not feedback_query:
                continue
                
            feedback_words = set(feedback_query.lower().split())
            
            # Calculer le Jaccard similarity
            intersection = len(query_words & feedback_words)
            union = len(query_words | feedback_words)
            
            if union > 0:
                similarity = intersection / union
                if similarity >= similarity_threshold:
                    similar_feedbacks.append({
                        'query': feedback_query,
                        'date': row.get('created_at'),
                        'count': row.get('count', 1),
                        'similarity': similarity
                    })
        
        # Trier par similarité décroissante
        similar_feedbacks.sort(key=lambda x: x['similarity'], reverse=True)
        
        return similar_feedbacks[:5]  # Retourner les 5 plus similaires
    
    except Exception as e:
        print(f"Erreur lors de la vérification des feedbacks similaires: {e}")
        return []


def get_negative_feedback_hashes() -> List[str]:
    """Récupère les hashs des requêtes ayant reçu des feedbacks négatifs"""
    if not USE_DATABASE:
        return []
    
    try:
        db = get_db()
        if not db.test_connection():
            return []
        
        query = """
        SELECT DISTINCT user_query_hash
        FROM classifications
        WHERE feedback_rating = 'down'
        AND user_query_hash IS NOT NULL
        AND date_classification >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
        
        results = db.execute_query(query, ())
        
        return [row.get('user_query_hash', '') for row in results if row.get('user_query_hash')]
    
    except Exception as e:
        print(f"Erreur lors de la récupération des hashs: {e}")
        return []


def should_invalidate_cache(query: str) -> bool:
    """
    Détermine si le cache doit être invalidé pour cette requête
    Retourne True si une requête similaire a reçu un feedback négatif
    """
    if not USE_DATABASE:
        return False
    
    try:
        query_hash = get_query_hash(query)
        negative_hashes = get_negative_feedback_hashes()
        
        # Vérifier si le hash exact existe
        if query_hash in negative_hashes:
            return True
        
        # Vérifier les requêtes similaires
        similar_feedbacks = check_similar_negative_feedbacks(query, similarity_threshold=0.6)
        return len(similar_feedbacks) > 0
    
    except Exception as e:
        print(f"Erreur lors de la vérification du cache: {e}")
        return False


def get_feedback_stats(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Récupère les statistiques des feedbacks depuis la table classifications"""
    if not USE_DATABASE:
        return {}
    
    try:
        db = get_db()
        if not db.test_connection():
            return {}
        
        if user_id:
            query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN feedback_rating = 'up' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN feedback_rating = 'down' THEN 1 ELSE 0 END) as negative
            FROM classifications
            WHERE user_id = %s AND feedback_rating IS NOT NULL
            """
            results = db.execute_query(query, (user_id,))
        else:
            query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN feedback_rating = 'up' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN feedback_rating = 'down' THEN 1 ELSE 0 END) as negative
            FROM classifications
            WHERE feedback_rating IS NOT NULL
            """
            results = db.execute_query(query, ())
        
        if results and len(results) > 0:
            row = results[0]
            total = row.get('total', 0) or 0
            positive = row.get('positive', 0) or 0
            negative = row.get('negative', 0) or 0
            
            return {
                'total': total,
                'positive': positive,
                'negative': negative,
                'satisfaction_rate': (positive / total * 100) if total > 0 else 0
            }
        
        return {'total': 0, 'positive': 0, 'negative': 0, 'satisfaction_rate': 0}
    
    except Exception as e:
        print(f"Erreur lors de la récupération des statistiques: {e}")
        return {'total': 0, 'positive': 0, 'negative': 0, 'satisfaction_rate': 0}

