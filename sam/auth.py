"""
Module d'authentification pour l'application de classification tarifaire
"""
import bcrypt
import json
import os
from pathlib import Path
from datetime import datetime
import streamlit as st


def get_users_file():
    """Retourne le chemin du fichier users.json"""
    current_dir = Path(__file__).parent
    return current_dir / "users.json"


def load_users():
    """Charge la liste des utilisateurs depuis users.json"""
    users_file = get_users_file()
    try:
        if users_file.exists():
            with open(users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        st.error(f"Erreur lors du chargement des utilisateurs: {e}")
    return []


def save_users(users):
    """Sauvegarde la liste des utilisateurs dans users.json"""
    users_file = get_users_file()
    try:
        with open(users_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde: {e}")
        return False


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


def authenticate_user(identifiant: str, password: str) -> dict | None:
    """
    Authentifie un utilisateur avec son identifiant et mot de passe.
    Retourne l'utilisateur si l'authentification réussit, None sinon.
    """
    users = load_users()
    for user in users:
        if user.get('identifiant_user') == identifiant:
            # Vérifier le statut du compte
            if user.get('statut') != 'actif':
                return None
            
            # Vérifier le mot de passe
            stored_password = user.get('password_hash') or user.get('mot_de_passe')
            if stored_password and verify_password(password, stored_password):
                # Mettre à jour la dernière connexion
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
    users = load_users()
    
    # Vérifier si l'identifiant existe déjà
    if any(u.get('identifiant_user') == identifiant_user for u in users):
        return False, "Cet identifiant existe déjà"
    
    # Vérifier si l'email existe déjà
    if any(u.get('email') == email for u in users):
        return False, "Cet email existe déjà"
    
    # Vérifier la longueur du mot de passe
    if len(password) < 6:
        return False, "Le mot de passe doit contenir au moins 6 caractères"
    
    # Créer le nouvel utilisateur
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


def get_current_user() -> dict | None:
    """Retourne l'utilisateur actuellement connecté depuis la session"""
    return st.session_state.get('user')


def is_authenticated() -> bool:
    """Vérifie si un utilisateur est authentifié"""
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
    st.rerun()


def initialize_default_users():
    """Initialise les utilisateurs par défaut si le fichier n'existe pas"""
    users_file = get_users_file()
    if not users_file.exists():
        default_users = [
            {
                "user_id": 1,
                "nom_user": "Admin Principal",
                "identifiant_user": "admin",
                "email": "admin@douane.ci",
                "password_hash": hash_password("admin123"),  # Mot de passe par défaut
                "statut": "actif",
                "is_admin": True,
                "date_creation": "2025-01-01T00:00:00Z",
                "derniere_connexion": datetime.now().isoformat()
            },
            {
                "user_id": 2,
                "nom_user": "Agent Douanes",
                "identifiant_user": "agent.douanes",
                "email": "agent@douane.ci",
                "password_hash": hash_password("agent123"),  # Mot de passe par défaut
                "statut": "actif",
                "is_admin": False,
                "date_creation": "2025-01-02T00:00:00Z",
                "derniere_connexion": "2025-01-07T14:30:00Z"
            }
        ]
        save_users(default_users)
        return default_users
    return []

