"""
Page de connexion pour l'application de classification tarifaire
"""
import streamlit as st
from auth_db import authenticate_user, initialize_default_users, is_authenticated
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
DOUANE_BLANC = "#FFFFFF"

# CSS style militaire/cartoon inspiré du design Dribbble
st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&family=Fredoka:wght@400;500;600;700&display=swap');
        
        * {{
            font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }}
        
        /* Fond principal vert militaire avec forme ondulée */
        .stApp {{
            background: {DOUANE_VERT};
            min-height: 100vh;
            position: relative;
            overflow-x: hidden;
        }}
        
        /* Centrer le conteneur de connexion */
        .main .block-container {{
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 2rem;
        }}
        
        /* Forme blanche ondulée en haut */
        .stApp::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 150px;
            background: white;
            clip-path: polygon(0 0, 100% 0, 100% 80%, 0 100%);
            z-index: 0;
        }}
        
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        
        /* Conteneur de connexion style cartoon */
        .login-container {{
            background: white;
            padding: 3rem;
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            max-width: 500px;
            width: 100%;
            border: 4px solid #2d5016;
            position: relative;
            z-index: 1;
            animation: fadeInUp 0.5s ease;
        }}
        
        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        .login-header {{
            text-align: center;
            margin-bottom: 2.5rem;
        }}
        
        .login-header h1 {{
            color: {DOUANE_VERT};
            font-family: 'Fredoka', sans-serif;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            margin-top: 0;
            text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.1);
        }}
        
        .login-header p {{
            color: #2d5016;
            font-size: 1.1rem;
            font-weight: 500;
            margin: 0.25rem 0;
        }}
        
        .login-header .subtitle {{
            font-size: 0.9rem;
            color: #666;
            font-weight: 400;
        }}
        
        /* Input style cartoon */
        .stTextInput > div > div > input {{
            background-color: white;
            color: {DOUANE_VERT};
            border: 3px solid {DOUANE_VERT};
            border-radius: 15px;
            padding: 1rem 1.25rem;
            font-family: 'Poppins', sans-serif;
            font-size: 1rem;
            font-weight: 500;
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }}
        
        .stTextInput > div > div > input:focus {{
            border-color: {DOUANE_OR};
            box-shadow: 0 4px 12px rgba(255, 215, 0, 0.3);
            outline: none;
        }}
        
        /* Labels style cartoon */
        .stTextInput label {{
            font-family: 'Fredoka', sans-serif;
            font-weight: 600;
            font-size: 1.1rem;
            color: {DOUANE_VERT};
        }}
        
        /* Boutons style cartoon */
        .stButton > button {{
            font-family: 'Fredoka', sans-serif;
            font-weight: 600;
            font-size: 1rem;
            border-radius: 15px;
            padding: 0.75rem 1.5rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            border: 3px solid #2d5016;
        }}
        
        /* Bouton Se connecter (doré comme la page d'accueil) - cible le premier bouton du formulaire */
        form[data-testid="stForm"] .stButton:first-of-type > button {{
            background: {DOUANE_OR};
            color: {DOUANE_VERT};
        }}
        
        form[data-testid="stForm"] .stButton:first-of-type > button:hover {{
            transform: translateY(-3px);
            background: #FFA500;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
        }}
        
        /* Bouton Annuler (blanc avec bordure) - cible le deuxième bouton du formulaire */
        form[data-testid="stForm"] .stButton:last-of-type > button {{
            background: white;
            color: {DOUANE_VERT};
        }}
        
        form[data-testid="stForm"] .stButton:last-of-type > button:hover {{
            transform: translateY(-3px);
            background: #f5f5f5;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
        }}
        
        /* Expander style cartoon */
        .streamlit-expanderHeader {{
            font-family: 'Fredoka', sans-serif;
            font-weight: 600;
            color: {DOUANE_VERT};
        }}
        
        .streamlit-expanderContent {{
            font-family: 'Poppins', sans-serif;
        }}
        
        /* Messages d'erreur/succès */
        .stAlert {{
            border-radius: 15px;
            border: 3px solid #2d5016;
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
        <p class="subtitle">Direction Générale des Douanes</p>
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
        cancel_button = st.form_submit_button("❌ Annuler", use_container_width=True)
        if cancel_button:
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

