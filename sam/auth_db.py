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

# Fonctions pour le fallback JSON (toujours disponibles)
def get_users_file():
    """Retourne le chemin du fichier users.json"""
    current_dir = Path(__file__).parent
    return current_dir / "users.json"

def load_users_json():
    """Charge la liste des utilisateurs depuis users.json"""
    users_file = get_users_file()
    try:
        if users_file.exists():
            with open(users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        st.error(f"Erreur lors du chargement des utilisateurs: {e}")
    return []

def save_users_json(users):
    """Sauvegarde la liste des utilisateurs dans users.json"""
    users_file = get_users_file()
    try:
        with open(users_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde: {e}")
        return False

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
    """Charge les utilisateurs depuis MySQL ou JSON"""
    if USE_DATABASE:
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
        except Exception as e:
            st.warning(f"⚠️ Erreur de connexion MySQL, utilisation de JSON: {e}")
    
    # Fallback vers JSON
    if not USE_DATABASE:
        return load_users_json()
    return []


def save_users(users: list) -> bool:
    """Sauvegarde les utilisateurs dans MySQL ou JSON"""
    if USE_DATABASE:
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
        except Exception as e:
            st.warning(f"⚠️ Erreur MySQL, utilisation de JSON: {e}")
    
    # Fallback vers JSON
    if not USE_DATABASE:
        return save_users_json(users)
    return False


def save_session_to_cookie(user: Dict[str, Any]):
    """Sauvegarde l'identifiant de l'utilisateur dans un cookie pour la persistance"""
    import streamlit as st
    identifiant = user.get('identifiant_user', '')
    if identifiant:
        st.markdown(f"""
        <script>
            // Sauvegarder l'identifiant dans un cookie (expire dans 7 jours)
            const expires = new Date();
            expires.setTime(expires.getTime() + (7 * 24 * 60 * 60 * 1000));
            document.cookie = "streamlit_user_id={identifiant}; expires=" + expires.toUTCString() + "; path=/";
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
        
        st.session_state['_restore_attempted'] = True
        
        # Utiliser JavaScript pour lire le cookie et le passer via query params
        # Cette approche nécessite un rafraîchissement, donc on va utiliser une autre méthode
        # On va plutôt utiliser un script qui lit le cookie et recharge la page avec l'identifiant
        
        # Méthode alternative : utiliser un composant pour lire le cookie
        # Pour l'instant, on va utiliser une approche avec query params via JavaScript
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
                // Recharger la page avec l'identifiant dans l'URL pour que Python puisse le lire
                const url = new URL(window.location);
                url.searchParams.set('user_id', userId);
                window.history.replaceState({}, '', url);
                // Forcer un rerun de Streamlit
                window.location.reload();
            }
        </script>
        """, unsafe_allow_html=True)
        
        # Lire l'identifiant depuis les query params
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
                        # Nettoyer l'URL
                        st.query_params.clear()
            except Exception:
                pass
        
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
            st.warning(f"⚠️ Erreur MySQL, utilisation de JSON: {e}")
    
    # Fallback vers JSON
    users = load_users_json() if not USE_DATABASE else load_users()
    for user in users:
        if user.get('identifiant_user') == identifiant:
            if user.get('statut') != 'actif':
                return None
            
            stored_password = user.get('password_hash') or user.get('mot_de_passe')
            if stored_password and verify_password(password, stored_password):
                user['derniere_connexion'] = datetime.now().isoformat()
                save_users(users)
                return user
    return None


def create_user(nom_user: str, identifiant_user: str, email: str, 
                password: str, is_admin: bool = False) -> tuple[bool, str]:
    """
    Crée un nouvel utilisateur avec un mot de passe hashé.
    Retourne (success, message)
    """
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
                
                # Créer le nouvel utilisateur
                insert_query = """
                    INSERT INTO users (nom_user, identifiant_user, email, password_hash, statut, is_admin)
                    VALUES (%s, %s, %s, %s, 'actif', %s)
                """
                user_id = db.execute_insert(insert_query, (
                    nom_user, identifiant_user, email, hash_password(password), 1 if is_admin else 0
                ))
                
                return True, f"Utilisateur créé avec succès : {nom_user}"
        except Exception as e:
            st.warning(f"⚠️ Erreur MySQL, utilisation de JSON: {e}")
    
    # Fallback vers JSON
    users = load_users_json() if not USE_DATABASE else load_users()
    
    if any(u.get('identifiant_user') == identifiant_user for u in users):
        return False, "Cet identifiant existe déjà"
    
    if any(u.get('email') == email for u in users):
        return False, "Cet email existe déjà"
    
    if len(password) < 6:
        return False, "Le mot de passe doit contenir au moins 6 caractères"
    
    new_user = {
        "user_id": max([u.get('user_id', 0) for u in users], default=0) + 1,
        "nom_user": nom_user,
        "identifiant_user": identifiant_user,
        "email": email,
        "password_hash": hash_password(password),
        "statut": "actif",
        "is_admin": is_admin,
        "date_creation": datetime.now().isoformat(),
        "derniere_connexion": None
    }
    
    users.append(new_user)
    if save_users(users):
        return True, f"Utilisateur créé avec succès : {nom_user}"
    else:
        return False, "Erreur lors de la création de l'utilisateur"


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
    # Supprimer le cookie
    st.markdown("""
    <script>
        // Supprimer le cookie
        document.cookie = "streamlit_user_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    </script>
    """, unsafe_allow_html=True)
    st.rerun()


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
    
    # Fallback vers JSON
    users_file = get_users_file()
    if not users_file.exists():
        default_users = [
            {
                "user_id": 1,
                "nom_user": "Admin Principal",
                "identifiant_user": "admin",
                "email": "admin@douane.ci",
                "password_hash": hash_password("admin123"),
                "statut": "actif",
                "is_admin": True,
                "date_creation": "2025-01-01T00:00:00Z",
                "derniere_connexion": datetime.now().isoformat()
            }
        ]
        save_users_json(default_users)
        return default_users
    return []

