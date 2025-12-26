"""
Page de connexion pour l'application de classification tarifaire
"""
import streamlit as st
from auth_db import authenticate_user, initialize_default_users, is_authenticated, get_current_user
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

# CSS style inspiré de la page principale
st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&family=Fredoka:wght@400;500;600;700&display=swap');
        
        * {{
            font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }}
        
        /* Fond principal vert clair avec transition vers vert foncé en bas et accents jaunes */
        .stApp {{
            background: linear-gradient(180deg, #E8F5E9 0%, #C8E6C9 30%, {DOUANE_OR} 50%, #C8E6C9 70%, {DOUANE_VERT} 100%);
            min-height: 100vh;
            position: relative;
            overflow-x: hidden;
        }}
        
        /* Centrer le contenu */
        .main .block-container {{
            max-width: 1200px;
            padding: 1rem 2rem;
            padding-top: 0.5rem;
        }}
        
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        
        /* Cacher complètement la sidebar sur la page Login */
        [data-testid="stSidebar"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        
        /* Cacher le bouton pour ouvrir la sidebar */
        button[kind="header"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        
        [data-testid="baseButton-header"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        
        /* Boîte de bienvenue */
        .welcome-box {{
            background: white;
            padding: 2rem;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            border: 3px solid {DOUANE_VERT};
            border-top: 5px solid {DOUANE_OR};
            margin-bottom: 1.5rem;
            margin-top: 0.5rem;
            text-align: center;
            position: relative;
        }}
        
        .welcome-box::before {{
            content: '🐘';
            font-size: 3rem;
            position: absolute;
            top: -20px;
            left: 50%;
            transform: translateX(-50%);
            background: {DOUANE_OR};
            padding: 0.5rem;
            border-radius: 50%;
            border: 3px solid {DOUANE_VERT};
            box-shadow: 0 4px 12px rgba(255, 215, 0, 0.4);
        }}
        
        .welcome-text {{
            color: {DOUANE_VERT};
            font-size: 1.5rem;
            font-weight: 600;
            margin-top: 1.5rem;
            margin-bottom: 0.5rem;
        }}
        
        /* Boîte Direction Générale */
        .directorate-box {{
            background: white;
            padding: 3rem 2rem;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            border: 3px solid {DOUANE_VERT};
            border-left: 5px solid {DOUANE_OR};
            border-right: 5px solid {DOUANE_OR};
            margin-bottom: 2rem;
            text-align: center;
        }}
        
        .directorate-title {{
            color: {DOUANE_VERT};
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}
        
        .directorate-subtitle {{
            color: #666;
            font-size: 1.1rem;
            font-weight: 400;
        }}
        
        /* Conteneur de connexion */
        .login-container {{
            background: transparent;
            padding: 0;
            max-width: 500px;
            width: 100%;
            margin: 0 auto;
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
            margin-bottom: 1rem;
            background: transparent;
        }}
        
        .login-header h1 {{
            color: {DOUANE_VERT};
            font-family: 'Fredoka', sans-serif;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            margin-top: 0;
            background: transparent;
            text-shadow: 2px 2px 4px rgba(255, 215, 0, 0.3);
        }}
        
        .login-header p {{
            color: #666;
            font-size: 1rem;
            font-weight: 400;
            margin: 0.25rem 0;
            background: transparent;
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
        
        /* Formulaire dans une boîte blanche */
        form[data-testid="stForm"] {{
            background: white;
            padding: 2rem;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            border: 3px solid {DOUANE_VERT};
            border-top: 5px solid {DOUANE_OR};
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
        
        /* ============================================
           OPTIMISATIONS MOBILE - PAGE LOGIN
           ============================================ */
        
        @media screen and (max-width: 768px) {{
            .main .block-container {{
                padding: 0.5rem 1rem !important;
            }}
            
            .welcome-box {{
                padding: 1rem !important;
                margin-bottom: 1rem !important;
            }}
            
            .welcome-text {{
                font-size: 1.2rem !important;
            }}
            
            form[data-testid="stForm"] {{
                padding: 1.5rem !important;
            }}
            
            .login-header h1 {{
                font-size: 1.5rem !important;
            }}
            
            .login-header p {{
                font-size: 0.9rem !important;
            }}
        }}
        
        @media screen and (max-width: 480px) {{
            .main .block-container {{
                padding: 0.5rem !important;
            }}
            
            .welcome-box {{
                padding: 0.8rem !important;
            }}
            
            .welcome-text {{
                font-size: 1rem !important;
            }}
            
            form[data-testid="stForm"] {{
                padding: 1rem !important;
            }}
            
            .login-header h1 {{
                font-size: 1.2rem !important;
            }}
        }}
    </style>
""", unsafe_allow_html=True)

# Initialiser les utilisateurs par défaut si nécessaire
initialize_default_users()

# Restaurer la session depuis le cookie/query params si nécessaire
from auth_db import restore_session_from_cookie
restore_session_from_cookie()

# Si l'utilisateur est déjà connecté, rediriger vers l'application principale
if is_authenticated():
    # S'assurer que l'identifiant est dans les query params
    current_user = get_current_user()
    if current_user and not st.query_params.get('user_id'):
        st.query_params['user_id'] = current_user.get('identifiant_user', '')
    st.switch_page("app.py")

# Boîte de bienvenue
st.markdown("""
    <div class="welcome-box">
        <div class="welcome-text">Bienvenue dans Mosam - Classification Tarifaire CEDEAO</div>
    </div>
""", unsafe_allow_html=True)

# Conteneur de connexion
st.markdown('<div class="login-container">', unsafe_allow_html=True)

st.markdown("""
    <div class="login-header">
        <h1>🔐 Connexion</h1>
        <p>Veuillez vous connecter pour accéder au système</p>
    </div>
""", unsafe_allow_html=True)

# Formulaire de connexion
with st.form("login_form", clear_on_submit=False):
    identifiant = st.text_input("👤 Identifiant", placeholder="Entrez votre identifiant")
    password = st.text_input("🔒 Mot de passe", type="password", placeholder="Entrez votre mot de passe")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        submit_button = st.form_submit_button("Se connecter", use_container_width=True)
    with col2:
        cancel_button = st.form_submit_button("Annuler", use_container_width=True)
        if cancel_button:
            st.stop()
    
    if submit_button:
        if not identifiant or not password:
            st.error("⚠️ Veuillez remplir tous les champs")
        else:
            user = authenticate_user(identifiant, password)
            if user:
                # Stocker l'utilisateur dans la session (persistant)
                st.session_state['user'] = user
                # Sauvegarder dans un cookie pour la persistance après rafraîchissement
                from auth_db import save_session_to_cookie
                save_session_to_cookie(user)
                st.success(f"✅ Bienvenue {user.get('nom_user', identifiant)}!")
                st.rerun()
            else:
                st.error("❌ Identifiant ou mot de passe incorrect, ou compte inactif")

st.markdown('</div>', unsafe_allow_html=True)

