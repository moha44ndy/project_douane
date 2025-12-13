"""
Page de connexion pour l'application de classification tarifaire
"""
import streamlit as st
from auth import authenticate_user, initialize_default_users, is_authenticated
from pathlib import Path

# Configuration de la page
st.set_page_config(
    page_title="Connexion - Classification Tarifaire CEDEAO",
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Couleurs du thème
DOUANE_VERT = "#1B5E20"
DOUANE_OR = "#FFD700"

# CSS
st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');
        
        * {{
            font-family: 'Poppins', sans-serif;
        }}
        
        .stApp {{
            background: linear-gradient(135deg, {DOUANE_VERT} 0%, #2d5016 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        
        .login-container {{
            background: white;
            padding: 3rem;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
            max-width: 450px;
            width: 100%;
        }}
        
        .login-header {{
            text-align: center;
            margin-bottom: 2rem;
        }}
        
        .login-header h1 {{
            color: {DOUANE_VERT};
            margin-bottom: 0.5rem;
        }}
        
        .login-header p {{
            color: #666;
            font-size: 0.9rem;
        }}
    </style>
""", unsafe_allow_html=True)

# Initialiser les utilisateurs par défaut si nécessaire
initialize_default_users()

# Si l'utilisateur est déjà connecté, rediriger vers l'application principale
if is_authenticated():
    st.switch_page("app.py")

# Conteneur de connexion
st.markdown('<div class="login-container">', unsafe_allow_html=True)

st.markdown("""
    <div class="login-header">
        <h1>🔐 Connexion</h1>
        <p>Classification Tarifaire CEDEAO</p>
        <p style="font-size: 0.8rem; color: #999;">Direction Générale des Douanes</p>
    </div>
""", unsafe_allow_html=True)

# Formulaire de connexion
with st.form("login_form", clear_on_submit=False):
    identifiant = st.text_input("👤 Identifiant", placeholder="Entrez votre identifiant")
    password = st.text_input("🔒 Mot de passe", type="password", placeholder="Entrez votre mot de passe")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        submit_button = st.form_submit_button("🚀 Se connecter", use_container_width=True)
    with col2:
        if st.form_submit_button("❌ Annuler", use_container_width=True):
            st.stop()
    
    if submit_button:
        if not identifiant or not password:
            st.error("⚠️ Veuillez remplir tous les champs")
        else:
            user = authenticate_user(identifiant, password)
            if user:
                # Stocker l'utilisateur dans la session
                st.session_state['user'] = user
                st.success(f"✅ Bienvenue {user.get('nom_user', identifiant)}!")
                st.rerun()
            else:
                st.error("❌ Identifiant ou mot de passe incorrect, ou compte inactif")

st.markdown('</div>', unsafe_allow_html=True)

# Informations de test (à retirer en production)
with st.expander("ℹ️ Comptes par défaut (développement)"):
    st.info("""
    **Compte Administrateur:**
    - Identifiant: `admin`
    - Mot de passe: `admin123` (à changer après première connexion)
    
    **Compte Agent:**
    - Identifiant: `agent.douanes`
    - Mot de passe: `agent123` (à changer après première connexion)
    """)

