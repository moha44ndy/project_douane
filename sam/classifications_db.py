"""
Module de gestion des classifications avec support MySQL
Système de Classification Douanière CEDEAO
"""
import streamlit as st
from typing import Optional, Dict, Any, List
from datetime import datetime

# Essayer d'importer le module database
try:
    from database import get_db
    USE_DATABASE = True
except ImportError:
    USE_DATABASE = False


def convert_json_to_db_format(json_item: dict) -> dict:
    """Convertit un élément JSON vers le format de la base de données"""
    product = json_item.get("product", {})
    classification = json_item.get("classification", {})
    section_obj = classification.get("section", {})
    
    return {
        "description_produit": product.get("description", ""),
        "valeur_produit": product.get("value", "Non renseigné"),
        "origine_produit": product.get("origin", "Non renseigné"),
        "code_tarifaire": classification.get("code", ""),
        "section": section_obj.get("number") if isinstance(section_obj, dict) else str(section_obj) if section_obj else None,
        "chapitre": extract_chapter_from_code(classification.get("code", "")),
        "confidence_score": classification.get("confidence", 0),
        "taux_dd": classification.get("taux_dd") if classification.get("taux_dd") else None,
        "taux_rs": classification.get("taux_rs") if classification.get("taux_rs") else None,
        "taux_tva": classification.get("taux_tva") if classification.get("taux_tva") else None,
        "unite_mesure": classification.get("unite_mesure") if classification.get("unite_mesure") else None,
        "justification": classification.get("justification") if classification.get("justification") else None,
    }


def convert_db_to_json_format(db_row: dict) -> dict:
    """Convertit une ligne de la base de données vers le format JSON"""
    result = {
        "product": {
            "description": db_row.get("description_produit", ""),
            "value": db_row.get("valeur_produit", "Non renseigné"),
            "origin": db_row.get("origine_produit", "Non renseigné"),
        },
        "classification": {
            "code": db_row.get("code_tarifaire", ""),
            "section": {"number": db_row.get("section")} if db_row.get("section") else {},
            "confidence": float(db_row.get("confidence_score", 0)) if db_row.get("confidence_score") else 0,
            "justification": db_row.get("justification"),  # Récupérer la justification depuis la DB
            "taux_dd": db_row.get("taux_dd"),
            "taux_rs": db_row.get("taux_rs"),
            "taux_tva": db_row.get("taux_tva"),
            "unite_mesure": db_row.get("unite_mesure"),
        }
    }
    
    # Ajouter les métadonnées de la base de données
    if db_row.get("date_classification"):
        # Convertir datetime en string ISO
        date_val = db_row.get("date_classification")
        if isinstance(date_val, datetime):
            result["date_classification"] = date_val.isoformat()
        elif isinstance(date_val, str):
            result["date_classification"] = date_val
        else:
            result["date_classification"] = str(date_val)
    
    if db_row.get("id"):
        result["id"] = db_row.get("id")
    
    if db_row.get("user_id"):
        result["user_id"] = db_row.get("user_id")
    
    return result


def extract_chapter_from_code(code: str) -> Optional[str]:
    """Extrait le chapitre (2 premiers chiffres) du code tarifaire"""
    if not code:
        return None
    digits = ''.join(c for c in code if c.isdigit())
    if len(digits) >= 2:
        return digits[:2]
    return None


def get_current_user_id() -> Optional[int]:
    """Récupère l'ID de l'utilisateur actuel depuis la session"""
    try:
        user = st.session_state.get("user")
        if user and isinstance(user, dict):
            # Vérifier si user_id existe directement
            if "user_id" in user:
                user_id = user["user_id"]
                if isinstance(user_id, int):
                    return user_id
                elif isinstance(user_id, str) and user_id.isdigit():
                    return int(user_id)
            
            # Si on a identifiant_user, chercher dans la base de données
            if "identifiant_user" in user and USE_DATABASE:
                try:
                    db = get_db()
                    if db.test_connection():
                        query = "SELECT user_id FROM users WHERE identifiant_user = %s AND statut = 'actif' LIMIT 1"
                        result = db.execute_query(query, (user["identifiant_user"],))
                        if result and len(result) > 0:
                            return result[0]["user_id"]
                except Exception:
                    pass
        
        # Essayer de récupérer depuis query_params (qui contient identifiant_user, pas user_id)
        if "user_id" in st.query_params:
            identifiant = st.query_params.get("user_id")
            if identifiant and USE_DATABASE:
                try:
                    db = get_db()
                    if db.test_connection():
                        query = "SELECT user_id FROM users WHERE identifiant_user = %s AND statut = 'actif' LIMIT 1"
                        result = db.execute_query(query, (identifiant,))
                        if result and len(result) > 0:
                            return result[0]["user_id"]
                except Exception:
                    pass
    except Exception as e:
        # Log l'erreur pour debug
        import traceback
        print(f"Erreur dans get_current_user_id: {e}\n{traceback.format_exc()}")
    return None


def load_classifications(user_id: Optional[int] = None) -> List[dict]:
    """Charge les classifications depuis MySQL"""
    if not USE_DATABASE:
        st.error("❌ Base de données non disponible. Veuillez configurer MySQL.")
        return []
    
    try:
        db = get_db()
        if not db.test_connection():
            st.error("❌ Impossible de se connecter à la base de données.")
            return []
        
        # Si user_id est fourni, filtrer par utilisateur, sinon récupérer toutes
        if user_id:
            query = """
                SELECT * FROM classifications 
                WHERE user_id = %s 
                ORDER BY date_classification DESC
            """
            results = db.execute_query(query, (user_id,))
        else:
            query = """
                SELECT * FROM classifications 
                ORDER BY date_classification DESC
            """
            results = db.execute_query(query)
        
        # Convertir en format JSON
        return [convert_db_to_json_format(row) for row in results]
    
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement des classifications: {str(e)}")
        return []


def save_classification(json_item: dict, user_id: Optional[int] = None) -> tuple[bool, str]:
    """Sauvegarde une classification dans MySQL"""
    if not USE_DATABASE:
        return False, "Base de données non disponible. Veuillez configurer MySQL."
    
    if not user_id:
        user_id = get_current_user_id()
        if not user_id:
            return False, "Utilisateur non identifié. Veuillez vous connecter."
    
    try:
        db = get_db()
        if not db.test_connection():
            return False, "Impossible de se connecter à la base de données."
        
        data = convert_json_to_db_format(json_item)
        
        # Vérifier que les données essentielles sont présentes
        if not data.get("description_produit"):
            return False, "Description du produit manquante"
        if not data.get("code_tarifaire"):
            return False, "Code tarifaire manquant"
        
        # Toujours créer une nouvelle entrée (même si la même classification existe déjà)
        # Cela permet de compter toutes les requêtes, même celles qui viennent du cache
        # Insérer une nouvelle classification (avec RETURNING id pour PostgreSQL)
        try:
            from database import _get_db_type
            is_postgresql = (_get_db_type() == 'postgresql')
        except:
            is_postgresql = False
        
        if is_postgresql:
            insert_query = """
                INSERT INTO classifications 
                (user_id, description_produit, valeur_produit, origine_produit,
                 code_tarifaire, section, chapitre, confidence_score,
                 taux_dd, taux_rs, taux_tva, unite_mesure, justification)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
        else:
            insert_query = """
                INSERT INTO classifications 
                (user_id, description_produit, valeur_produit, origine_produit,
                 code_tarifaire, section, chapitre, confidence_score,
                 taux_dd, taux_rs, taux_tva, unite_mesure, justification)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
        # Debug: Afficher les données avant insertion
        print(f"DEBUG: Tentative d'insertion - user_id={user_id}")
        print(f"DEBUG: description={data['description_produit']}")
        print(f"DEBUG: code={data['code_tarifaire']}")
        print(f"DEBUG: section={data['section']}, chapitre={data['chapitre']}")
        print(f"DEBUG: taux_dd={data['taux_dd']}, taux_rs={data['taux_rs']}, taux_tva={data['taux_tva']}")
        
        last_id = db.execute_insert(
            insert_query,
            (
                user_id,
                data["description_produit"],
                data["valeur_produit"],
                data["origine_produit"],
                data["code_tarifaire"],
                data["section"],
                data["chapitre"],
                data["confidence_score"],
                data["taux_dd"],
                data["taux_rs"],
                data["taux_tva"],
                data["unite_mesure"],
                data["justification"],
            )
        )
        print(f"DEBUG: Insertion réussie - ID: {last_id}")
        
        # Vérifier que l'insertion a bien eu lieu
        verify_query = "SELECT id FROM classifications WHERE id = %s"
        verify_result = db.execute_query(verify_query, (last_id,))
        if verify_result:
            return True, f"Classification enregistrée avec succès (ID: {last_id})"
        else:
            return False, f"Insertion effectuée mais vérification échouée (ID: {last_id})"
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return False, f"Erreur lors de la sauvegarde: {str(e)}\nDétails: {error_details}"


def save_classifications(classifications: List[dict], user_id: Optional[int] = None) -> tuple[bool, str]:
    """Sauvegarde plusieurs classifications dans MySQL"""
    if not classifications:
        return True, "Aucune classification à sauvegarder"
    
    if not user_id:
        user_id = get_current_user_id()
        if not user_id:
            return False, "Utilisateur non identifié. Veuillez vous connecter."
    
    # Debug: Vérifier USE_DATABASE
    if not USE_DATABASE:
        return False, "Base de données non disponible. Veuillez configurer MySQL."
    
    success_count = 0
    error_count = 0
    error_messages = []
    
    for idx, classification in enumerate(classifications):
        try:
            # Debug: Vérifier la structure
            if not isinstance(classification, dict):
                error_count += 1
                error_messages.append(f"Entrée {idx+1}: n'est pas un dictionnaire (type: {type(classification)})")
                continue
            
            if "classification" not in classification or "product" not in classification:
                error_count += 1
                error_messages.append(f"Entrée {idx+1}: structure invalide (clés manquantes: classification={classification.get('classification')}, product={classification.get('product')})")
                continue
            
            print(f"DEBUG: Sauvegarde de l'entrée {idx+1}/{len(classifications)}")
            success, message = save_classification(classification, user_id)
            if success:
                success_count += 1
                print(f"DEBUG: Entrée {idx+1} sauvegardée avec succès: {message}")
            else:
                error_count += 1
                error_msg = f"Entrée {idx+1}: {message}"
                error_messages.append(error_msg)
                print(f"DEBUG: {error_msg}")
        except Exception as e:
            error_count += 1
            import traceback
            error_messages.append(f"Entrée {idx+1}: Erreur: {str(e)}\n{traceback.format_exc()}")
    
    if error_count == 0:
        return True, f"{success_count} classification(s) enregistrée(s) avec succès"
    else:
        error_detail = "; ".join(error_messages[:3])  # Limiter à 3 erreurs pour l'affichage
        return False, f"{success_count} réussie(s), {error_count} erreur(s). Détails: {error_detail}"


def delete_classifications_by_ids(classification_ids: List[int], user_id: Optional[int] = None) -> tuple[bool, str]:
    """Supprime des classifications spécifiques par leurs IDs"""
    if not USE_DATABASE:
        return False, "Base de données non disponible."
    
    if not classification_ids:
        return True, "Aucune classification à supprimer"
    
    try:
        db = get_db()
        if not db.test_connection():
            return False, "Impossible de se connecter à la base de données."
        
        # Vérifier que l'utilisateur est le propriétaire des classifications
        if not user_id:
            user_id = get_current_user_id()
        
        if not user_id:
            return False, "Utilisateur non identifié."
        
        # Vérifier que toutes les classifications appartiennent à l'utilisateur (syntaxe adaptée)
        try:
            from database import _get_db_type
            is_postgresql = (_get_db_type() == 'postgresql')
        except:
            is_postgresql = False
        
        if is_postgresql:
            check_query = """
                SELECT id FROM classifications 
                WHERE id = ANY(%s) AND user_id = %s
            """
            results = db.execute_query(check_query, (classification_ids, user_id))
            delete_query = "DELETE FROM classifications WHERE id = ANY(%s)"
            db.execute_update(delete_query, (classification_ids,))
        else:
            placeholders = ','.join(['%s'] * len(classification_ids))
            check_query = f"""
                SELECT id FROM classifications 
                WHERE id IN ({placeholders}) AND user_id = %s
            """
            results = db.execute_query(check_query, (*classification_ids, user_id))
            delete_query = f"DELETE FROM classifications WHERE id IN ({placeholders})"
            db.execute_update(delete_query, tuple(classification_ids))
        
        found_ids = [row.get('id') for row in results if row.get('id')]
        
        if len(found_ids) != len(classification_ids):
            return False, "Certaines classifications n'existent pas ou ne vous appartiennent pas."
        
        return True, f"{len(classification_ids)} classification(s) supprimée(s) avec succès"
    
    except Exception as e:
        return False, f"Erreur lors de la suppression: {str(e)}"


def clear_classifications(user_id: Optional[int] = None) -> tuple[bool, str]:
    """Supprime toutes les classifications d'un utilisateur (ou toutes si admin)"""
    if not USE_DATABASE:
        return False, "Base de données non disponible."
    
    try:
        db = get_db()
        if not db.test_connection():
            return False, "Impossible de se connecter à la base de données."
        
        if user_id:
            query = "DELETE FROM classifications WHERE user_id = %s"
            db.execute_update(query, (user_id,))
            return True, f"Classifications de l'utilisateur supprimées"
        else:
            # Seul un admin peut supprimer toutes les classifications
            user = st.session_state.get("user")
            if user and user.get("is_admin"):
                query = "DELETE FROM classifications"
                db.execute_update(query)
                return True, "Toutes les classifications ont été supprimées"
            else:
                return False, "Seuls les administrateurs peuvent supprimer toutes les classifications"
    
    except Exception as e:
        return False, f"Erreur lors de la suppression: {str(e)}"


def get_classification_stats(user_id: Optional[int] = None) -> dict:
    """Récupère les statistiques des classifications"""
    if not USE_DATABASE:
        return {}
    
    try:
        db = get_db()
        if not db.test_connection():
            return {}
        
        if user_id:
            total_query = "SELECT COUNT(*) as total FROM classifications WHERE user_id = %s"
            today_query = """
                SELECT COUNT(*) as total FROM classifications 
                WHERE user_id = %s 
                AND DATE(date_classification) = CURDATE()
            """
            total_result = db.execute_query(total_query, (user_id,))
            today_result = db.execute_query(today_query, (user_id,))
        else:
            total_query = "SELECT COUNT(*) as total FROM classifications"
            today_query = """
                SELECT COUNT(*) as total FROM classifications 
                WHERE DATE(date_classification) = CURDATE()
            """
            total_result = db.execute_query(total_query)
            today_result = db.execute_query(today_query)
        
        return {
            "total": total_result[0]["total"] if total_result else 0,
            "today": today_result[0]["total"] if today_result else 0,
        }
    
    except Exception as e:
        st.error(f"Erreur lors de la récupération des statistiques: {str(e)}")
        return {}


# Fonctions de compatibilité avec l'ancien code
def load_table_data() -> List[dict]:
    """Charge les classifications (compatibilité avec l'ancien code)"""
    user_id = get_current_user_id()
    return load_classifications(user_id)


def save_table_data(data: List[dict]) -> bool:
    """Sauvegarde les classifications (compatibilité avec l'ancien code)"""
    user_id = get_current_user_id()
    if not user_id:
        st.error("Utilisateur non identifié. Veuillez vous connecter.")
        return False
    
    # Sauvegarder dans session_state pour compatibilité
    st.session_state["table_products"] = data
    
    # Sauvegarder dans MySQL
    success, message = save_classifications(data, user_id)
    if not success:
        st.error(message)
    return success

