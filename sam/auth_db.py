"""
Module d'authentification avec support MySQL
Système de Classification Douanière CEDEAO
"""
import bcrypt
import json
import os
from pathlib import Path
from datetime import datetime
import streamlit as st
from typing import Optional, Dict, Any

# Note: Les fonctions JSON ont été supprimées - utilisation exclusive de MySQL

# Essayer d'importer le module database
try:
    from database import get_db
    USE_DATABASE = True
except ImportError:
    USE_DATABASE = False


def hash_password(password: str) -> str:
    """Hash un mot de passe avec bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Vérifie si un mot de passe correspond au hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


# ============================================================
# FONCTIONS AVEC SUPPORT MYSQL
# ============================================================

def load_users() -> list:
    """Charge les utilisateurs depuis MySQL uniquement"""
    if not USE_DATABASE:
        st.error("❌ Base de données non disponible. Veuillez configurer MySQL.")
        return []
    
    try:
        db = get_db()
        if db.test_connection():
            query = "SELECT * FROM users ORDER BY user_id"
            users = db.execute_query(query)
            # Convertir en format compatible avec l'ancien code
            result = []
            for user in users or []:
                result.append({
                    'user_id': user['user_id'],
                    'nom_user': user['nom_user'],
                    'identifiant_user': user['identifiant_user'],
                    'email': user['email'],
                    'password_hash': user['password_hash'],
                    'statut': user['statut'],
                    'is_admin': bool(user['is_admin']),
                    'date_creation': user['date_creation'].isoformat() if hasattr(user['date_creation'], 'isoformat') else str(user['date_creation']),
                    'derniere_connexion': user['derniere_connexion'].isoformat() if user['derniere_connexion'] and hasattr(user['derniere_connexion'], 'isoformat') else (str(user['derniere_connexion']) if user['derniere_connexion'] else None)
                })
            return result
        else:
            st.error("❌ Impossible de se connecter à la base de données MySQL.")
            return []
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement des utilisateurs depuis MySQL: {e}")
        return []


def save_users(users: list) -> bool:
    """Sauvegarde les utilisateurs dans MySQL uniquement"""
    if not USE_DATABASE:
        st.error("❌ Base de données non disponible. Impossible de sauvegarder les utilisateurs.")
        return False
    
    try:
        db = get_db()
        if db.test_connection():
            # Mettre à jour chaque utilisateur
            for user in users:
                query = """
                    UPDATE users 
                    SET nom_user = %s, email = %s, password_hash = %s, 
                        statut = %s, is_admin = %s, derniere_connexion = %s
                    WHERE user_id = %s
                """
                params = (
                    user.get('nom_user'),
                    user.get('email'),
                    user.get('password_hash'),
                    user.get('statut', 'actif'),
                    1 if user.get('is_admin') else 0,
                    user.get('derniere_connexion'),
                    user.get('user_id')
                )
                db.execute_update(query, params)
            return True
        else:
            st.error("❌ Impossible de se connecter à la base de données MySQL.")
            return False
    except Exception as e:
        st.error(f"❌ Erreur lors de la sauvegarde des utilisateurs dans MySQL: {e}")
        return False


def save_session_to_cookie(user: Dict[str, Any]):
    """Sauvegarde l'identifiant de l'utilisateur dans un cookie pour la persistance"""
    import streamlit as st
    identifiant = user.get('identifiant_user', '')
    if identifiant:
        # Sauvegarder aussi dans query params pour la restauration immédiate
        st.query_params['user_id'] = identifiant
        st.markdown(f"""
        <script>
            // Sauvegarder l'identifiant dans un cookie (expire dans 7 jours)
            const expires = new Date();
            expires.setTime(expires.getTime() + (7 * 24 * 60 * 60 * 1000));
            document.cookie = "streamlit_user_id={identifiant}; expires=" + expires.toUTCString() + "; path=/; SameSite=Lax";
        </script>
        """, unsafe_allow_html=True)

def restore_session_from_cookie():
    """Restaure la session depuis le cookie si elle existe"""
    import streamlit as st
    try:
        # Si la session existe déjà, ne rien faire
        if 'user' in st.session_state and st.session_state.get('user') is not None:
            return
        
        # Vérifier si on a déjà essayé de restaurer (éviter les boucles infinies)
        if st.session_state.get('_restore_attempted', False):
            return
        
        # D'abord, vérifier les query params (si on vient d'un rafraîchissement avec cookie)
        user_id_from_url = st.query_params.get('user_id', None)
        if user_id_from_url and USE_DATABASE:
            try:
                db = get_db()
                if db.test_connection():
                    query = "SELECT * FROM users WHERE identifiant_user = %s AND statut = 'actif'"
                    users = db.execute_query(query, (user_id_from_url,))
                    if users and len(users) > 0:
                        user = users[0]
                        # Convertir au format compatible
                        st.session_state['user'] = {
                            'user_id': user['user_id'],
                            'nom_user': user['nom_user'],
                            'identifiant_user': user['identifiant_user'],
                            'email': user['email'],
                            'password_hash': user['password_hash'],
                            'statut': user['statut'],
                            'is_admin': bool(user['is_admin']),
                            'date_creation': user['date_creation'].isoformat() if hasattr(user['date_creation'], 'isoformat') else str(user['date_creation']),
                            'derniere_connexion': user['derniere_connexion'].isoformat() if user['derniere_connexion'] and hasattr(user['derniere_connexion'], 'isoformat') else (str(user['derniere_connexion']) if user['derniere_connexion'] else None)
                        }
                        # Ne pas nettoyer l'URL - garder les query params pour la persistance lors du rechargement
                        # Les query params seront conservés dans l'URL pour permettre la restauration rapide
                        return
            except Exception:
                pass
        
        # Si pas de query params, utiliser JavaScript pour lire le cookie et ajouter les query params
        st.session_state['_restore_attempted'] = True
        st.markdown("""
        <script>
            function getCookie(name) {
                const value = `; ${document.cookie}`;
                const parts = value.split(`; ${name}=`);
                if (parts.length === 2) return parts.pop().split(';').shift();
                return null;
            }
            const userId = getCookie('streamlit_user_id');
            if (userId && !window.location.search.includes('user_id=')) {
                // Ajouter l'identifiant dans l'URL pour que Python puisse le lire
                const url = new URL(window.location);
                url.searchParams.set('user_id', userId);
                // Recharger la page avec les query params pour restaurer la session
                window.location.href = url.toString();
            }
        </script>
        """, unsafe_allow_html=True)
        
    except Exception:
        pass

def authenticate_user(identifiant: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authentifie un utilisateur avec son identifiant et mot de passe.
    Retourne l'utilisateur si l'authentification réussit, None sinon.
    """
    if USE_DATABASE:
        try:
            db = get_db()
            if db.test_connection():
                query = "SELECT * FROM users WHERE identifiant_user = %s AND statut = 'actif'"
                users = db.execute_query(query, (identifiant,))
                
                if users and len(users) > 0:
                    user = users[0]
                    stored_password = user.get('password_hash')
                    
                    if stored_password and verify_password(password, stored_password):
                        # Mettre à jour la dernière connexion
                        update_query = "UPDATE users SET derniere_connexion = NOW() WHERE user_id = %s"
                        db.execute_update(update_query, (user['user_id'],))
                        
                        # Retourner au format compatible
                        return {
                            'user_id': user['user_id'],
                            'nom_user': user['nom_user'],
                            'identifiant_user': user['identifiant_user'],
                            'email': user['email'],
                            'password_hash': user['password_hash'],
                            'statut': user['statut'],
                            'is_admin': bool(user['is_admin']),
                            'date_creation': user['date_creation'].isoformat() if hasattr(user['date_creation'], 'isoformat') else str(user['date_creation']),
                            'derniere_connexion': datetime.now().isoformat()
                        }
        except Exception as e:
            st.error(f"❌ Erreur lors de l'authentification MySQL: {e}")
            return None
    
    # Si la base de données n'est pas disponible, retourner None
    if not USE_DATABASE:
        st.error("❌ Base de données non disponible. Impossible de s'authentifier.")
        return None
    
    return None


def create_user(nom_user: str, identifiant_user: str, email: str, 
                password: str, is_admin: bool = False) -> tuple[bool, str]:
    """
    Crée un nouvel utilisateur avec un mot de passe hashé.
    Retourne (success, message)
    """
    # Toujours essayer d'utiliser la base de données en premier si disponible
    if USE_DATABASE:
        try:
            db = get_db()
            if db.test_connection():
                # Vérifier si l'identifiant existe déjà
                check_query = "SELECT user_id FROM users WHERE identifiant_user = %s OR email = %s"
                existing = db.execute_query(check_query, (identifiant_user, email))
                
                if existing:
                    return False, "Cet identifiant ou email existe déjà"
                
                # Vérifier la longueur du mot de passe
                if len(password) < 6:
                    return False, "Le mot de passe doit contenir au moins 6 caractères"
                
                # Créer le nouvel utilisateur dans la base de données
                insert_query = """
                    INSERT INTO users (nom_user, identifiant_user, email, password_hash, statut, is_admin)
                    VALUES (%s, %s, %s, %s, 'actif', %s)
                """
                
                # Debug: Afficher les données avant insertion
                print(f"DEBUG: Création utilisateur - nom={nom_user}, identifiant={identifiant_user}, email={email}")
                
                user_id = db.execute_insert(insert_query, (
                    nom_user, identifiant_user, email, hash_password(password), 1 if is_admin else 0
                ))
                
                print(f"DEBUG: Utilisateur créé avec ID: {user_id}")
                
                # Vérifier que l'insertion a bien eu lieu
                verify_query = "SELECT user_id, nom_user, identifiant_user, email, statut, is_admin FROM users WHERE user_id = %s"
                verify_result = db.execute_query(verify_query, (user_id,))
                
                if verify_result:
                    user_data = verify_result[0]
                    print(f"DEBUG: Vérification réussie - Utilisateur trouvé: {user_data}")
                    return True, f"Utilisateur créé avec succès : {nom_user} (ID: {user_id})"
                else:
                    return False, f"Erreur : L'utilisateur a été créé (ID: {user_id}) mais la vérification a échoué"
            else:
                # Si la connexion échoue, retourner une erreur au lieu de fallback JSON
                return False, "Erreur de connexion à la base de données. Veuillez vérifier la configuration."
        except Exception as e:
            # Si une erreur survient, retourner l'erreur au lieu de fallback JSON
            return False, f"Erreur lors de la création de l'utilisateur : {str(e)}"
    
    # Plus de fallback vers JSON - uniquement MySQL
    if not USE_DATABASE:
        return False, "Base de données non disponible. Veuillez configurer MySQL pour créer des utilisateurs."
    
    # Si on arrive ici, c'est qu'il y a un problème
    return False, "Impossible de créer l'utilisateur. Base de données non disponible."


def update_user(user_id: int, nom_user: str = None, identifiant_user: str = None, 
                email: str = None, password: str = None, statut: str = None, 
                is_admin: bool = None) -> tuple[bool, str]:
    """
    Met à jour les informations d'un utilisateur existant.
    Retourne (success, message)
    """
    if not USE_DATABASE:
        return False, "Base de données non disponible. Veuillez configurer MySQL."
    
    try:
        db = get_db()
        if not db.test_connection():
            return False, "Erreur de connexion à la base de données."
        
        # Vérifier que l'utilisateur existe
        check_query = "SELECT * FROM users WHERE user_id = %s"
        existing_user = db.execute_query(check_query, (user_id,))
        if not existing_user:
            return False, "Utilisateur introuvable."
        
        existing_user = existing_user[0]
        
        # Construire la requête de mise à jour dynamiquement
        update_fields = []
        params = []
        
        if nom_user is not None:
            update_fields.append("nom_user = %s")
            params.append(nom_user)
        
        if identifiant_user is not None:
            # Vérifier que l'identifiant n'est pas déjà utilisé par un autre utilisateur
            check_identifiant = "SELECT user_id FROM users WHERE identifiant_user = %s AND user_id != %s"
            existing_identifiant = db.execute_query(check_identifiant, (identifiant_user, user_id))
            if existing_identifiant:
                return False, "Cet identifiant est déjà utilisé par un autre utilisateur."
            update_fields.append("identifiant_user = %s")
            params.append(identifiant_user)
        
        if email is not None:
            # Vérifier que l'email n'est pas déjà utilisé par un autre utilisateur
            check_email = "SELECT user_id FROM users WHERE email = %s AND user_id != %s"
            existing_email = db.execute_query(check_email, (email, user_id))
            if existing_email:
                return False, "Cet email est déjà utilisé par un autre utilisateur."
            update_fields.append("email = %s")
            params.append(email)
        
        if password is not None and password.strip():
            # Vérifier la longueur du mot de passe
            if len(password) < 6:
                return False, "Le mot de passe doit contenir au moins 6 caractères."
            update_fields.append("password_hash = %s")
            params.append(hash_password(password))
        
        if statut is not None:
            update_fields.append("statut = %s")
            params.append(statut)
        
        if is_admin is not None:
            update_fields.append("is_admin = %s")
            params.append(1 if is_admin else 0)
        
        if not update_fields:
            return False, "Aucune modification à apporter."
        
        # Ajouter user_id aux paramètres pour la clause WHERE
        params.append(user_id)
        
        # Construire et exécuter la requête
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = %s"
        db.execute_update(update_query, tuple(params))
        
        return True, f"Utilisateur mis à jour avec succès (ID: {user_id})"
        
    except Exception as e:
        return False, f"Erreur lors de la mise à jour de l'utilisateur : {str(e)}"


def get_current_user() -> Optional[Dict[str, Any]]:
    """Retourne l'utilisateur actuellement connecté depuis la session"""
    # Essayer de restaurer la session depuis les cookies si elle n'existe pas
    if 'user' not in st.session_state or st.session_state.get('user') is None:
        restore_session_from_cookie()
    return st.session_state.get('user')


def is_authenticated() -> bool:
    """Vérifie si un utilisateur est authentifié"""
    # Essayer de restaurer la session depuis les cookies si elle n'existe pas
    if 'user' not in st.session_state or st.session_state.get('user') is None:
        restore_session_from_cookie()
    return 'user' in st.session_state and st.session_state.get('user') is not None


def is_admin() -> bool:
    """Vérifie si l'utilisateur actuel est un administrateur"""
    user = get_current_user()
    return user is not None and user.get('is_admin', False)


def require_auth():
    """Redirige vers la page de connexion si l'utilisateur n'est pas authentifié"""
    if not is_authenticated():
        st.switch_page("pages/Login.py")


def require_admin():
    """Redirige vers la page principale si l'utilisateur n'est pas admin"""
    require_auth()
    if not is_admin():
        st.error("⚠️ Accès refusé : Vous devez être administrateur pour accéder à cette page.")
        st.stop()


def logout():
    """Déconnecte l'utilisateur actuel"""
    if 'user' in st.session_state:
        del st.session_state['user']
    # Supprimer les query params
    if 'user_id' in st.query_params:
        del st.query_params['user_id']
    # Supprimer le cookie
    st.markdown("""
    <script>
        // Supprimer le cookie
        document.cookie = "streamlit_user_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    </script>
    """, unsafe_allow_html=True)
    # Rediriger vers la page de login
    st.switch_page("pages/Login.py")


def initialize_default_users():
    """Initialise les utilisateurs par défaut si nécessaire"""
    if USE_DATABASE:
        try:
            db = get_db()
            if db.test_connection():
                # Vérifier si des utilisateurs existent
                query = "SELECT COUNT(*) as count FROM users"
                result = db.execute_query(query)
                if result and result[0]['count'] == 0:
                    # Créer l'admin par défaut
                    success, message = create_user(
                        "Admin Principal",
                        "admin",
                        "admin@douane.ci",
                        "admin123",
                        True
                    )
                    # Ignorer l'erreur si l'utilisateur existe déjà (peut arriver en cas de race condition)
                    if not success and "existe déjà" not in message:
                        # Seulement logger si c'est une autre erreur
                        pass
                return
        except Exception as e:
            # Ignorer les erreurs silencieusement pour ne pas bloquer l'application
            pass
    
    # Plus de fallback vers JSON - uniquement MySQL
    if not USE_DATABASE:
        st.error("❌ Base de données non disponible. Impossible d'initialiser les utilisateurs par défaut.")
        return

