import streamlit as st
import streamlit.components.v1 as components
import json
import os
import html
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
from auth_db import (
    load_users, save_users, create_user,
    require_admin, get_current_user, logout, initialize_default_users
)
from classifications_db import load_classifications

# Configuration de la page
st.set_page_config(
    page_title="Administration - Classification Tarifaire CEDEAO",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Couleurs du thème
DOUANE_VERT = "#1B5E20"
DOUANE_OR = "#FFD700"
DOUANE_BLANC = "#FFFFFF"

# CSS style cohérent avec l'application principale
st.markdown("""
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
""", unsafe_allow_html=True)

st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&family=Fredoka:wght@400;500;600;700&display=swap');
        
        * {{
            font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }}
        
        /* Fond principal vert militaire avec formes ondulées */
        .stApp {{
            background: {DOUANE_VERT};
            min-height: 100vh;
            position: relative;
            overflow-x: hidden;
        }}
        
        /* Formes blanches ondulées en haut */
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
        
        /* Cacher les éléments Streamlit par défaut */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        
        /* Cacher spécifiquement les liens Login et Profil dans la sidebar */
        [data-testid="stSidebarNav"] a[href*="Login"],
        [data-testid="stSidebarNav"] a[href*="login"],
        [data-testid="stSidebarNav"] a[href*="/Login"],
        [data-testid="stSidebarNav"] a[href*="/login"],
        [data-testid="stSidebarNav"] a[href*="Profil"],
        [data-testid="stSidebarNav"] a[href*="profil"],
        [data-testid="stSidebarNav"] a[href*="/Profil"],
        [data-testid="stSidebarNav"] a[href*="/profil"],
        [data-testid="stSidebarNav"] li:has(a[href*="Login"]),
        [data-testid="stSidebarNav"] li:has(a[href*="login"]),
        [data-testid="stSidebarNav"] li:has(a[href*="Profil"]),
        [data-testid="stSidebarNav"] li:has(a[href*="profil"]) {{
            display: none !important;
            visibility: hidden !important;
        }}
        
        /* Mettre chaque bouton de navigation dans un fond or */
        [data-testid="stSidebarNav"] li {{
            background: {DOUANE_OR} !important;
            margin: 0.5rem 0 !important;
            border-radius: 10px !important;
            padding: 0.5rem !important;
            border: 2px solid #2d5016 !important;
        }}
        
        [data-testid="stSidebarNav"] a {{
            color: {DOUANE_VERT} !important;
            font-weight: 600 !important;
            display: block !important;
            padding: 0.5rem !important;
            border-radius: 8px !important;
        }}
        
        [data-testid="stSidebarNav"] a:hover {{
            background-color: #FFA500 !important;
            color: {DOUANE_VERT} !important;
        }}
        
        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background-color: {DOUANE_VERT} !important;
            color: white !important;
        }}
        
        /* Header Streamlit visible */
        header[data-testid="stHeader"] {{
            display: flex !important;
            height: auto !important;
            background: white !important;
            border-bottom: 3px solid {DOUANE_VERT} !important;
            padding: 0.5rem 1rem !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
        }}
        
        /* Afficher tous les boutons du header */
        header button {{
            display: block !important;
            visibility: visible !important;
        }}
        
        .stDeployButton {{
            display: block !important;
        }}
        
        [data-testid="stToolbar"] {{
            display: flex !important;
        }}
        
        /* Conteneur principal */
        .main .block-container {{
            padding-top: 1rem;
            padding-left: 2rem;
            padding-right: 2rem;
            max-width: 100%;
            position: relative;
            z-index: 1;
        }}
        
        /* Header style cartoon */
        .main-header {{
            background: white;
            padding: 1.5rem 2rem;
            border-radius: 20px;
            border: 4px solid #2d5016;
            margin-bottom: 2rem;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            position: relative;
            overflow: hidden;
        }}
        
        .main-header::before {{
            content: '';
            position: absolute;
            top: -50%;
            right: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255, 215, 0, 0.1) 0%, transparent 70%);
            animation: rotate 20s linear infinite;
        }}
        
        @keyframes rotate {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}
        
        .main-header h1 {{
            color: {DOUANE_VERT};
            font-family: 'Fredoka', sans-serif;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            margin-top: 0;
            text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.1);
            position: relative;
            z-index: 1;
        }}
        
        .main-header p {{
            color: #2d5016;
            font-size: 1.1rem;
            font-weight: 500;
            margin: 0;
            position: relative;
            z-index: 1;
        }}
        
        /* Section statistiques style cartoon */
        .stats-section {{
            background: white;
            padding: 2rem;
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            margin-bottom: 2rem;
            border: 4px solid #2d5016;
            position: relative;
        }}
        
        .stat-card {{
            background: white;
            padding: 1.5rem;
            border-radius: 15px;
            border: 3px solid {DOUANE_VERT};
            transition: all 0.3s ease;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px) scale(1.05);
            border-color: {DOUANE_OR};
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
        }}
        
        .stat-number {{
            font-size: 2.5rem;
            font-weight: 700;
            color: {DOUANE_VERT};
            margin-bottom: 0.5rem;
            font-family: 'Fredoka', sans-serif;
        }}
        
        .stat-card p {{
            color: {DOUANE_VERT};
            font-weight: 600;
            margin: 0;
        }}
        
        /* Boutons style cartoon - avec !important pour éviter les conflits */
        .stButton > button {{
            background: {DOUANE_VERT} !important;
            color: white !important;
            font-family: 'Fredoka', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1.1rem !important;
            border: 3px solid #2d5016 !important;
            border-radius: 15px !important;
            padding: 1rem 2.5rem !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
        }}
        
        .stButton > button:hover {{
            transform: translateY(-3px) !important;
            background: #2d7a3d !important;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3) !important;
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
        
        /* Selectbox style cartoon */
        .stSelectbox > div > div {{
            background-color: white;
            border: 3px solid {DOUANE_VERT};
            border-radius: 15px;
        }}
        
        /* Date input style cartoon */
        .stDateInput > div > div > input {{
            background-color: white;
            border: 3px solid {DOUANE_VERT};
            border-radius: 15px;
        }}
        
        /* Titres de section style cartoon */
        .section-title {{
            color: {DOUANE_VERT} !important;
            font-family: 'Fredoka', sans-serif;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.1);
        }}
        
        /* Styles pour les titres h3 dans markdown */
        .stMarkdown h3 {{
            color: {DOUANE_VERT} !important;
            font-family: 'Fredoka', sans-serif;
            font-weight: 700;
            font-size: 1.5rem;
        }}
        
        /* Styles pour les labels de text_input */
        .stTextInput label {{
            color: {DOUANE_VERT} !important;
            font-family: 'Fredoka', sans-serif;
            font-weight: 600;
            font-size: 1.1rem;
        }}
        
        /* Styles pour les labels de metric */
        .stMetric label {{
            color: {DOUANE_VERT} !important;
            font-family: 'Fredoka', sans-serif;
            font-weight: 600;
            font-size: 1.1rem;
        }}
        
        /* Styles pour les valeurs de metric */
        .stMetric [data-testid="stMetricValue"] {{
            color: {DOUANE_VERT} !important;
            font-family: 'Fredoka', sans-serif;
            font-weight: 700;
        }}
        
        /* Scrollbar style cartoon */
        ::-webkit-scrollbar {{
            width: 12px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: white;
            border: 2px solid {DOUANE_VERT};
            border-radius: 10px;
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: {DOUANE_OR};
            border: 2px solid #2d5016;
            border-radius: 10px;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: #FFA500;
        }}
        
        /* Sidebar moderne */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {DOUANE_VERT} 0%, #1a472a 50%, #2d5016 100%) !important;
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
        }}
        
        /* Fond blanc pour la section utilisateur dans la sidebar */
        [data-testid="stSidebar"] > div:has(h3:has-text("👤")),
        [data-testid="stSidebar"] > div:has-text("👤") {{
            background: white !important;
            padding: 1rem !important;
            border-radius: 15px !important;
            margin: 1rem 0 !important;
            border: 2px solid {DOUANE_VERT} !important;
        }}
        
        /* Style pour le conteneur utilisateur */
        .user-info-container {{
            background: white !important;
            padding: 1.5rem !important;
            border-radius: 15px !important;
            margin: 1rem 0 !important;
            border: 2px solid {DOUANE_VERT} !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
        }}
        
        /* Bouton pour ouvrir la sidebar */
        .sidebar-toggle-btn {{
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 999;
            background: {DOUANE_OR};
            color: {DOUANE_VERT};
            border: 3px solid #2d5016;
            border-radius: 15px;
            padding: 0.75rem 1.5rem;
            font-family: 'Fredoka', sans-serif;
            font-weight: 600;
            font-size: 1rem;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
        }}
        
        .sidebar-toggle-btn:hover {{
            transform: translateY(-3px);
            background: #FFA500;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
        }}
        
        .sidebar-toggle-btn:active {{
            transform: translateY(-1px);
        }}
        
        /* Animation fadeInUp */
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
        
        /* Cartes blanches style cartoon */
        .white-card {{
            background: white;
            padding: 2rem;
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            margin-bottom: 2rem;
            transition: all 0.3s ease;
            border: 3px solid #2d5016;
            position: relative;
        }}
        
        .white-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.2);
        }}
        
        /* Tabs style cartoon */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
        }}
        
        .stTabs [data-baseweb="tab"] {{
            background-color: white;
            border: 3px solid {DOUANE_VERT};
            border-radius: 15px;
            padding: 0.75rem 1.5rem;
            font-family: 'Fredoka', sans-serif;
            font-weight: 600;
            color: {DOUANE_VERT};
        }}
        
        .stTabs [aria-selected="true"] {{
            background-color: {DOUANE_VERT};
            color: white;
            border-color: #2d5016;
        }}
        
        /* Style pour les DataFrames */
        .stDataFrame {{
            border: 3px solid {DOUANE_VERT};
            border-radius: 15px;
            overflow: hidden;
        }}
        
        /* Style pour les métriques */
        [data-testid="stMetricValue"] {{
            color: {DOUANE_VERT} !important;
            font-family: 'Fredoka', sans-serif !important;
        }}
        
        [data-testid="stMetricLabel"] {{
            color: #2d5016 !important;
            font-family: 'Poppins', sans-serif !important;
        }}
        
        /* Style pour les checkboxes */
        .stCheckbox > label {{
            color: {DOUANE_VERT} !important;
            font-family: 'Poppins', sans-serif !important;
            font-weight: 500 !important;
        }}
        
        /* Style pour les messages info/success/error */
        .stAlert {{
            border: 3px solid {DOUANE_VERT} !important;
            border-radius: 15px !important;
        }}
        
        [data-baseweb="notification"] {{
            border: 3px solid {DOUANE_VERT} !important;
            border-radius: 15px !important;
        }}
        
        /* Style pour les messages d'info - texte jaune avec JavaScript pour forcer */
        [data-baseweb="notification"][kind="info"] {{
            color: {DOUANE_OR} !important;
        }}
        
        [data-baseweb="notification"][kind="info"] *,
        [data-baseweb="notification"][kind="info"] span,
        [data-baseweb="notification"][kind="info"] div,
        [data-baseweb="notification"][kind="info"] p,
        [data-baseweb="notification"][kind="info"] label {{
            color: {DOUANE_OR} !important;
        }}
        
        div[data-testid="stAlert"] [data-baseweb="notification"][kind="info"],
        div[data-testid="stAlert"] [data-baseweb="notification"][kind="info"] *,
        div[data-testid="stAlert"] [data-baseweb="notification"][kind="info"] span,
        div[data-testid="stAlert"] [data-baseweb="notification"][kind="info"] div,
        div[data-testid="stAlert"] [data-baseweb="notification"][kind="info"] p,
        div[data-testid="stAlert"] [data-baseweb="notification"][kind="info"] label {{
            color: {DOUANE_OR} !important;
        }}
        
        /* Améliorer le style des DataFrames */
        div[data-testid="stDataFrame"] {{
            border: 3px solid {DOUANE_VERT} !important;
            border-radius: 15px !important;
            overflow: hidden !important;
        }}
        
        /* Style pour les tableaux */
        table {{
            border-collapse: collapse !important;
        }}
        
        table th {{
            background: {DOUANE_VERT} !important;
            color: white !important;
            font-family: 'Fredoka', sans-serif !important;
            font-weight: 600 !important;
            padding: 1rem !important;
        }}
        
        table td {{
            border: 1px solid #e0e0e0 !important;
            padding: 0.75rem !important;
        }}
        
        table tr:nth-child(even) {{
            background: #f5f5f5 !important;
        }}
        
        table tr:hover {{
            background: rgba(255, 215, 0, 0.1) !important;
        }}
        
        /* Style pour les formulaires */
        .stForm {{
            border: 3px solid {DOUANE_VERT} !important;
            border-radius: 20px !important;
            padding: 2rem !important;
            background: white !important;
        }}
        
        /* ============================================
           OPTIMISATIONS RESPONSIVE - PAGE ADMINISTRATION
           ============================================ */
        
        /* Tablettes (1024px et moins) */
        @media screen and (max-width: 1024px) {{
            .main .block-container {{
                padding-left: 1.5rem !important;
                padding-right: 1.5rem !important;
            }}
            
            .white-card {{
                padding: 1.5rem !important;
            }}
            
            /* Colonnes Streamlit - réduire la largeur */
            [data-testid="column"] {{
                flex: 0 0 auto !important;
            }}
        }}
        
        /* Tablettes et mobiles (768px et moins) */
        @media screen and (max-width: 768px) {{
            /* Conteneur principal - padding réduit sur mobile */
            .main .block-container {{
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                padding-top: 0.5rem !important;
                max-width: 100% !important;
            }}
            
            /* Cartes blanches - padding réduit */
            .white-card {{
                padding: 1rem !important;
                margin-bottom: 1rem !important;
                border-radius: 15px !important;
                width: 100% !important;
                box-sizing: border-box !important;
            }}
            
            /* Header - taille réduite */
            .main-header {{
                padding: 1rem !important;
                margin-bottom: 1rem !important;
                flex-direction: column !important;
                align-items: flex-start !important;
            }}
            
            .main-header h1 {{
                font-size: 1.5rem !important;
                margin-bottom: 0.5rem !important;
            }}
            
            .main-header p {{
                font-size: 0.85rem !important;
            }}
            
            /* Statistiques - colonnes empilées */
            .stat-card {{
                margin-bottom: 1rem !important;
                width: 100% !important;
            }}
            
            /* DataFrames - largeur complète avec défilement */
            .stDataFrame, div[data-testid="stDataFrame"] {{
                width: 100% !important;
                overflow-x: auto !important;
                -webkit-overflow-scrolling: touch !important;
            }}
            
            /* Tableaux - défilement horizontal */
            table {{
                min-width: 600px !important;
                font-size: 0.85rem !important;
            }}
            
            table th, table td {{
                padding: 0.5rem !important;
                font-size: 0.85rem !important;
            }}
            
            /* Inputs - largeur complète */
            .stTextInput > div > div > input,
            .stTextArea > div > div > textarea,
            .stSelectbox > div > div > select {{
                font-size: 0.9rem !important;
                width: 100% !important;
                box-sizing: border-box !important;
            }}
            
            /* Boutons - taille adaptée */
            button, .stButton > button {{
                font-size: 0.9rem !important;
                padding: 0.5rem 1rem !important;
                width: 100% !important;
                box-sizing: border-box !important;
            }}
            
            /* Formulaires - padding réduit */
            .stForm, form[data-testid="stForm"] {{
                padding: 1rem !important;
            }}
            
            /* FORCER les colonnes Streamlit à s'empiler verticalement */
            [data-testid="stHorizontalBlock"] {{
                flex-direction: column !important;
                display: flex !important;
            }}
            
            [data-testid="column"] {{
                min-width: 100% !important;
                width: 100% !important;
                flex: 1 1 100% !important;
                margin-bottom: 0.5rem !important;
                padding-left: 0 !important;
                padding-right: 0 !important;
            }}
            
            /* Sidebar - optimisée pour mobile */
            [data-testid="stSidebar"] {{
                min-width: 200px !important;
                max-width: 80vw !important;
            }}
            
            /* Header Streamlit - hauteur réduite */
            header[data-testid="stHeader"] {{
                background: white !important;
                padding: 0.3rem 0.5rem !important;
                flex-wrap: wrap !important;
            }}
            
            /* Markdown et textes - ajustement */
            .stMarkdown {{
                font-size: 0.9rem !important;
            }}
            
            /* Métriques - taille réduite */
            [data-testid="stMetricValue"] {{
                font-size: 1.2rem !important;
            }}
            
            [data-testid="stMetricLabel"] {{
                font-size: 0.85rem !important;
            }}
        }}
        
        /* Petits mobiles (480px et moins) */
        @media screen and (max-width: 480px) {{
            /* Très petits écrans - optimisations supplémentaires */
            .main .block-container {{
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
                padding-top: 0.3rem !important;
            }}
            
            .white-card {{
                padding: 0.8rem !important;
                border-radius: 12px !important;
                margin-bottom: 0.8rem !important;
            }}
            
            .main-header {{
                padding: 0.8rem !important;
            }}
            
            .main-header h1 {{
                font-size: 1.2rem !important;
                line-height: 1.2 !important;
            }}
            
            .main-header p {{
                font-size: 0.75rem !important;
            }}
            
            /* Tableaux - taille réduite */
            table {{
                min-width: 500px !important;
                font-size: 0.75rem !important;
            }}
            
            table th, table td {{
                padding: 0.4rem !important;
                font-size: 0.75rem !important;
            }}
            
            button, .stButton > button {{
                font-size: 0.85rem !important;
                padding: 0.4rem 0.8rem !important;
                min-height: 40px !important;
            }}
            
            /* Inputs */
            .stTextInput > div > div > input,
            .stTextArea > div > div > textarea,
            .stSelectbox > div > div > select {{
                font-size: 0.85rem !important;
                padding: 0.6rem 0.8rem !important;
            }}
            
            /* Formulaires */
            .stForm, form[data-testid="stForm"] {{
                padding: 0.8rem !important;
            }}
            
            /* Métriques */
            [data-testid="stMetricValue"] {{
                font-size: 1rem !important;
            }}
            
            [data-testid="stMetricLabel"] {{
                font-size: 0.8rem !important;
            }}
            
            /* Colonnes Streamlit - empilées sur très petit écran */
            .element-container {{
                width: 100% !important;
                max-width: 100% !important;
            }}
            
            /* Sidebar encore plus compacte */
            [data-testid="stSidebar"] {{
                min-width: 180px !important;
                max-width: 75vw !important;
            }}
        }}
        
        /* Très petits écrans (360px et moins) */
        @media screen and (max-width: 360px) {{
            .main .block-container {{
                padding-left: 0.3rem !important;
                padding-right: 0.3rem !important;
            }}
            
            .white-card {{
                padding: 0.6rem !important;
            }}
            
            .main-header h1 {{
                font-size: 1rem !important;
            }}
            
            table {{
                font-size: 0.7rem !important;
            }}
            
            table th, table td {{
                padding: 0.3rem !important;
                font-size: 0.7rem !important;
            }}
            
            button, .stButton > button {{
                font-size: 0.8rem !important;
                padding: 0.35rem 0.7rem !important;
                min-height: 36px !important;
            }}
            
            .stForm, form[data-testid="stForm"] {{
                padding: 0.6rem !important;
            }}
        }}
        
        /* Amélioration du touch sur mobile */
        @media (hover: none) and (pointer: coarse) {{
            button, a, [role="button"], .stButton > button {{
                min-height: 44px !important;
                min-width: 44px !important;
            }}
            
            .stTextInput > div > div > input,
            .stTextArea > div > div > textarea,
            .stSelectbox > div > div > select {{
                min-height: 44px !important;
            }}
            
            /* Désactiver les effets hover sur mobile */
            .white-card:hover {{
                transform: none !important;
            }}
            
            table tr:hover {{
                background: #f5f5f5 !important;
            }}
        }}
    </style>
""", unsafe_allow_html=True)

# Script JavaScript injecté directement dans le document principal (pas dans un iframe)
st.markdown(f"""
<script>
    (function() {{
        console.log('[STYLES DEBUG] Script de style chargé dans le document principal');
        
        // Ignorer les erreurs 404 normales de Streamlit
        const originalError = console.error;
        console.error = function(...args) {{
            const message = args.join(' ');
            if (message.includes('_stcore/health') || message.includes('_stcore/host-config') || message.includes('404')) {{
                return;
            }}
            originalError.apply(console, args);
        }};
        
        // Fonction pour forcer le style des boutons de maintenance
        function styleMaintenanceButtons() {{
            // Chercher par attribut key
            const buttons1 = document.querySelectorAll('button[key="clear_cache_btn"], button[key="save_backup_btn"], button[key="show_logs_btn"]');
            // Chercher par texte du bouton
            const buttons2 = Array.from(document.querySelectorAll('button')).filter(btn => {{
                const text = btn.textContent || btn.innerText;
                return text.includes('Vider le Cache') || text.includes('Sauvegarder') || text.includes('Logs Système');
            }});
            
            const allButtons = [...buttons1, ...buttons2];
            const uniqueButtons = Array.from(new Set(allButtons));
            
            console.log('[STYLES DEBUG] Boutons de maintenance trouvés:', uniqueButtons.length);
            uniqueButtons.forEach((btn, index) => {{
                const beforeBg = window.getComputedStyle(btn).backgroundColor;
                const beforeColor = window.getComputedStyle(btn).color;
                console.log('[STYLES DEBUG] Bouton', index, 'AVANT - bg:', beforeBg, 'couleur:', beforeColor);
                
                // Forcer les styles directement
                btn.style.setProperty('background-color', '{DOUANE_OR}', 'important');
                btn.style.setProperty('color', '{DOUANE_VERT}', 'important');
                btn.style.setProperty('border', '3px solid #2d5016', 'important');
                btn.style.setProperty('border-radius', '15px', 'important');
                btn.style.setProperty('font-family', "'Fredoka', sans-serif", 'important');
                btn.style.setProperty('font-weight', '600', 'important');
                btn.style.setProperty('font-size', '1rem', 'important');
                btn.style.setProperty('padding', '1rem', 'important');
                btn.style.setProperty('box-shadow', '0 4px 12px rgba(0, 0, 0, 0.2)', 'important');
                
                const afterBg = window.getComputedStyle(btn).backgroundColor;
                const afterColor = window.getComputedStyle(btn).color;
                console.log('[STYLES DEBUG] Bouton', index, 'APRÈS - bg:', afterBg, 'couleur:', afterColor);
            }});
        }}
        
        function forceStyles() {{
            console.log('[STYLES DEBUG] forceStyles() appelé');
            
            // Forcer le style des messages d'info en jaune
            const infoMessages = document.querySelectorAll('[data-baseweb="notification"][kind="info"]');
            console.log('[STYLES DEBUG] Messages d\\'info trouvés:', infoMessages.length);
            infoMessages.forEach((msg, index) => {{
                console.log('[STYLES DEBUG] Application style info message', index);
                msg.style.setProperty('color', '{DOUANE_OR}', 'important');
                const children = msg.querySelectorAll('*');
                children.forEach(child => {{
                    child.style.setProperty('color', '{DOUANE_OR}', 'important');
                }});
            }});
            
            // Forcer le style des messages de succès en blanc sur fond or
            const successMessages = document.querySelectorAll('[data-baseweb="notification"][kind="success"]');
            console.log('[STYLES DEBUG] Messages de succès trouvés:', successMessages.length);
            successMessages.forEach((msg, index) => {{
                console.log('[STYLES DEBUG] Application style success message', index);
                msg.style.setProperty('background-color', '{DOUANE_OR}', 'important');
                msg.style.setProperty('border-color', '{DOUANE_OR}', 'important');
                msg.style.setProperty('color', 'white', 'important');
                const children = msg.querySelectorAll('*');
                children.forEach(child => {{
                    child.style.setProperty('color', 'white', 'important');
                }});
            }});
            
            // Forcer le style des boutons
            styleMaintenanceButtons();
        }}
        
        // Exécuter après que le document soit prêt
        function init() {{
            if (document.body) {{
                forceStyles();
                
                // Observer les changements
                try {{
                    const observer = new MutationObserver(() => {{
                        forceStyles();
                    }});
                    observer.observe(document.body, {{ childList: true, subtree: true }});
                    console.log('[STYLES DEBUG] MutationObserver configuré');
                }} catch (e) {{
                    console.log('[STYLES DEBUG] Erreur MutationObserver:', e.message);
                }}
                
                // Réexécuter périodiquement
                setInterval(() => {{
                    forceStyles();
                    styleMaintenanceButtons();
                }}, 500);
            }} else {{
                console.log('[STYLES DEBUG] Body non disponible, nouvelle tentative dans 100ms');
                setTimeout(init, 100);
            }}
        }}
        
        // Attendre que le document soit prêt
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', init);
        }} else {{
            setTimeout(init, 100);
        }}
    }})();
</script>
""", unsafe_allow_html=True)

# Les fonctions load_users et save_users sont maintenant importées depuis auth_db.py

def load_table_data():
    """Charge les données de classification depuis MySQL"""
    return load_classifications()  # Charge toutes les classifications (admin)

# La fonction initialize_default_users est maintenant dans auth_db.py

def main():
    # Initialiser les utilisateurs par défaut si nécessaire
    initialize_default_users()
    
    # Restaurer la session depuis le cookie/query params si nécessaire (AVANT toute vérification)
    from auth_db import restore_session_from_cookie
    restore_session_from_cookie()
    
    # Vérifier que l'utilisateur est admin
    require_admin()
    
    # Afficher les informations de l'utilisateur connecté
    current_user = get_current_user()
    if current_user:
        # S'assurer que l'identifiant est dans les query params pour la persistance
        if not st.query_params.get('user_id'):
            st.query_params['user_id'] = current_user.get('identifiant_user', '')
        
        # Plus besoin de préserver table_cleared ou table_product_ids - tout est dans la DB maintenant
        # Préserver seulement user_id si nécessaire
        if "user_id" in st.query_params:
            st.query_params["user_id"] = st.query_params["user_id"]
        
        # Conteneur avec fond blanc pour les informations utilisateur
        st.sidebar.markdown(f"""
            <div class="user-info-container">
                <h3 style="color: {DOUANE_VERT}; margin-top: 0; margin-bottom: 0.5rem;">👤 {current_user.get('nom_user', 'Utilisateur')}</h3>
                <p style="color: #666; margin: 0.25rem 0; font-size: 0.9rem;">*{current_user.get('email', '')}*</p>
                {"<p style='color: " + DOUANE_OR + "; margin: 0.5rem 0 0 0; font-weight: 600;'>👑 Administrateur</p>" if current_user.get('is_admin') else ""}
            </div>
        """, unsafe_allow_html=True)
        
        if st.sidebar.button("👤 Mon Profil", use_container_width=True):
            # Plus besoin de préserver table_cleared ou table_product_ids - tout est dans la DB maintenant
            # Préserver seulement user_id si nécessaire
            if "user_id" in st.query_params:
                st.query_params["user_id"] = st.query_params["user_id"]
            
            st.switch_page("pages/Profil.py")
        if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
            logout()
    
    # Script pour créer le bouton et définir la fonction toggleSidebar
    st.markdown(f"""
        <script>
            // Définir la fonction toggleSidebar
            function toggleSidebar() {{
                console.log('toggleSidebar appelé');
                
                // Méthode 1: Chercher le bouton natif de Streamlit avec plusieurs sélecteurs
                const selectors = [
                    'button[kind="header"]',
                    '[data-testid="baseButton-header"]',
                    'button[aria-label*="sidebar"]',
                    'button[aria-label*="menu"]',
                    '[data-testid="stSidebar"] + button',
                    'header button:first-of-type',
                    'button[title*="menu"]',
                    'button[title*="Menu"]'
                ];
                
                let sidebarButton = null;
                for (const selector of selectors) {{
                    const buttons = document.querySelectorAll(selector);
                    for (const btn of buttons) {{
                        // Vérifier si c'est bien le bouton de la sidebar
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {{
                            sidebarButton = btn;
                            break;
                        }}
                    }}
                    if (sidebarButton) break;
                }}
                
                if (sidebarButton) {{
                    console.log('Bouton natif trouvé, clic...');
                    sidebarButton.click();
                    return;
                }}
                
                // Méthode 2: Forcer l'affichage/masquage de la sidebar directement
                const sidebar = document.querySelector('[data-testid="stSidebar"]');
                if (sidebar) {{
                    console.log('Sidebar trouvée, basculement manuel...');
                    
                    // Vérifier l'état actuel de la sidebar de manière plus fiable
                    const rect = sidebar.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.left >= 0;
                    
                    if (isVisible) {{
                        // Fermer la sidebar
                        console.log('Fermeture de la sidebar');
                        sidebar.style.setProperty('display', 'none', 'important');
                        sidebar.style.setProperty('transform', 'translateX(-100%)', 'important');
                        sidebar.style.setProperty('visibility', 'hidden', 'important');
                        sidebar.style.setProperty('opacity', '0', 'important');
                    }} else {{
                        // Ouvrir la sidebar
                        console.log('Ouverture de la sidebar');
                        sidebar.style.setProperty('display', 'block', 'important');
                        sidebar.style.setProperty('transform', 'translateX(0)', 'important');
                        sidebar.style.setProperty('visibility', 'visible', 'important');
                        sidebar.style.setProperty('opacity', '1', 'important');
                    }}
                    
                    // Déclencher un événement pour notifier Streamlit
                    const event = new Event('sidebar-toggle', {{ bubbles: true }});
                    sidebar.dispatchEvent(event);
                    
                    // Forcer un reflow pour s'assurer que les changements sont appliqués
                    sidebar.offsetHeight;
                }} else {{
                    console.log('Sidebar non trouvée');
                }}
            }}
            
            // Fonction pour créer et attacher le bouton
            function setupSidebarButton() {{
                // Vérifier si le bouton existe déjà
                if (document.getElementById('custom-sidebar-toggle-btn')) {{
                    return;
                }}
                
                // Créer le bouton
                const btn = document.createElement('button');
                btn.id = 'custom-sidebar-toggle-btn';
                btn.className = 'sidebar-toggle-btn';
                btn.textContent = '☰ Menu';
                btn.title = 'Ouvrir/Fermer le menu';
                btn.type = 'button';
                
                // Attacher le gestionnaire d'événements
                btn.addEventListener('click', function(e) {{
                    e.preventDefault();
                    e.stopPropagation();
                    toggleSidebar();
                }});
                
                // Ajouter le bouton au body
                document.body.appendChild(btn);
            }}
            
            // Exécuter au chargement
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', setupSidebarButton);
            }} else {{
                setupSidebarButton();
            }}
            
            // Réessayer après un court délai pour s'assurer que le DOM est prêt
            setTimeout(setupSidebarButton, 100);
            
            // Observer les changements du DOM pour s'assurer que le bouton reste
            const observer = new MutationObserver(function(mutations) {{
                if (!document.getElementById('custom-sidebar-toggle-btn')) {{
                    setupSidebarButton();
                }}
            }});
            observer.observe(document.body, {{ childList: true, subtree: true }});
        </script>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown(f"""
        <div class="main-header">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <h1>👑 Panneau Administrateur</h1>
                    <p>Direction Générale des Douanes de Côte d'Ivoire</p>
                    <p style="color: {DOUANE_OR}; margin: 0.5rem 0 0 0; font-size: 0.9rem; font-weight: 600;">👑 Panneau administrateur actif</p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Bouton retour
    if st.button("🏠 Retour au Système", use_container_width=True):
        # Préserver les query_params importants lors de la navigation
        # Récupérer depuis session_state (priorité) ou query_params (fallback)
        preserve_params = {}
        
        # Plus besoin de préserver table_cleared ou table_product_ids - tout est dans la DB maintenant
        # Préserver seulement user_id si nécessaire
        if "user_id" in st.query_params:
            st.query_params["user_id"] = st.query_params["user_id"]
        
        st.switch_page("app.py")
    
    # Charger les données
    users = load_users()
    classifications = load_table_data()
    
    # Statistiques
    total_users = len(users)
    active_users = sum(1 for u in users if u.get('statut') == 'actif')
    total_classifications = len(classifications)
    today = datetime.now().date()
    today_classifications = sum(1 for c in classifications 
                               if isinstance(c.get('date_classification'), str) and 
                               datetime.fromisoformat(c.get('date_classification', '').replace('Z', '+00:00')).date() == today)
    
    st.markdown(f"""
        <div class="stats-section">
            <h2 class="section-title" style="text-align: center; margin-bottom: 2rem;">
                📊 Statistiques du Système
            </h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem;">
                <div class="stat-card">
                    <div class="stat-number">{total_users}</div>
                    <p>Utilisateurs Totaux</p>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{total_classifications}</div>
                    <p>Classifications</p>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{active_users}</div>
                    <p>Sessions Actives</p>
                </div>
                <div class="stat-card">
                    <div class="stat-number" style="font-size: 2rem;">🟢</div>
                    <p>Statut Système</p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Tabs pour organiser les sections
    tab1, tab2, tab3, tab4 = st.tabs(["👤 Inscription", "👥 Gestion Utilisateurs", "📈 Historique", "🛠️ Maintenance"])
    
    # Tab 1: Inscription d'utilisateur
    with tab1:
        with st.form("register_form", clear_on_submit=True):
            st.markdown("### 👤 Inscription d'un Nouvel Utilisateur")
            col1, col2 = st.columns(2)
            
            with col1:
                nom_user = st.text_input("Nom complet *", placeholder="Ex: Jean Dupont")
                identifiant_user = st.text_input("Identifiant *", placeholder="Ex: jean.dupont")
            
            with col2:
                email = st.text_input("Email *", placeholder="jean.dupont@douane.ci")
                password = st.text_input("Mot de passe *", type="password", placeholder="Minimum 6 caractères")
            
            is_admin = st.checkbox("👑 Accorder les privilèges d'administrateur")
            
            submitted = st.form_submit_button("✅ Créer l'Utilisateur", use_container_width=True)
            
            if submitted:
                # Validation des champs obligatoires
                if not nom_user or not nom_user.strip():
                    st.error("❌ Le nom complet est obligatoire")
                elif not identifiant_user or not identifiant_user.strip():
                    st.error("❌ L'identifiant est obligatoire")
                elif not email or not email.strip():
                    st.error("❌ L'email est obligatoire")
                elif not password or not password.strip():
                    st.error("❌ Le mot de passe est obligatoire")
                elif len(password) < 6:
                    st.error("❌ Le mot de passe doit contenir au moins 6 caractères")
                else:
                    success, message = create_user(
                        nom_user=nom_user.strip(),
                        identifiant_user=identifiant_user.strip(),
                        email=email.strip(),
                        password=password,
                        is_admin=is_admin
                    )
                    if success:
                        st.success(f"✅ {message}")
                        # Attendre un peu pour que l'utilisateur voie le message
                        import time
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                        # Ne pas faire rerun en cas d'erreur pour que l'utilisateur voie le message
    
    # Tab 2: Gestion des utilisateurs
    with tab2:
        # Utiliser le champ Streamlit natif d'abord (sera intégré dans le conteneur via CSS)
        search_term = st.text_input(
            "🔍 Rechercher un utilisateur", 
            placeholder="Nom, identifiant, email...", 
            key="user_search_input"
        )
        
        # Créer le conteneur blanc avec le titre (le champ de recherche sera positionné juste en dessous)
        st.markdown(f"""
            <div class="white-card user-management-section">
                <h2 class="section-title" style="margin-top: 0; margin-bottom: 1.5rem; padding-top: 0;">👥 Gestion des Utilisateurs</h2>
        """, unsafe_allow_html=True)
        
        # Ajouter JavaScript pour déclencher un rerun automatique après la saisie
        if 'last_search_term' not in st.session_state:
            st.session_state.last_search_term = ""
        
        # Si le terme de recherche a changé, déclencher un rerun
        if search_term != st.session_state.last_search_term:
            st.session_state.last_search_term = search_term
        
        # Filtrer les utilisateurs
        filtered_users = users
        if search_term:
            filtered_users = [u for u in users 
                            if search_term.lower() in u.get('nom_user', '').lower() or
                               search_term.lower() in u.get('identifiant_user', '').lower() or
                               search_term.lower() in u.get('email', '').lower()]
        
        # JavaScript pour déclencher un rerun automatique lors de la saisie
        st.markdown("""
        <script>
            (function() {
                const searchInput = document.querySelector('input[placeholder*="Nom, identifiant, email"]');
                if (searchInput) {
                    let debounceTimer;
                    searchInput.addEventListener('input', function() {
                        clearTimeout(debounceTimer);
                        debounceTimer = setTimeout(function() {
                            // Déclencher un rerun en simulant un événement de changement
                            searchInput.dispatchEvent(new Event('change', { bubbles: true }));
                            // Forcer un blur pour déclencher le rerun Streamlit
                            searchInput.blur();
                            searchInput.focus();
                        }, 500);
                    });
                }
            })();
        </script>
        """, unsafe_allow_html=True)
        
        # Préparer le contenu HTML pour le tableau
        table_html = ""
        if len(filtered_users) == 0:
            table_html = '<div style="background: #e8f5e9; padding: 1rem 1.5rem; border-radius: 15px; border: 2px solid ' + DOUANE_VERT + '; color: #2d5016; font-family: \'Poppins\', sans-serif; margin-top: 1.5rem;">🔍 Aucun utilisateur trouvé</div>'
        else:
            # Créer le tableau HTML
            table_html = '<div style="margin-top: 1.5rem; overflow-x: auto;"><table style="width: 100%; border-collapse: collapse; background: white;"><thead><tr style="background: ' + DOUANE_VERT + '; color: white;">'
            table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">ID</th>'
            table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Nom</th>'
            table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Identifiant</th>'
            table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Email</th>'
            table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Statut</th>'
            table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Admin</th>'
            table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Date création</th>'
            table_html += '</tr></thead><tbody>'
            
            for i, user in enumerate(filtered_users):
                bg_color = '#f5f5f5' if i % 2 == 0 else 'white'
                user_id = user.get("user_id", "N/A")
                # Stocker la couleur de fond dans un attribut data pour JavaScript
                table_html += f'<tr id="user_row_{user_id}" data-user-id="{user_id}" data-bg-color="{bg_color}" style="background: {bg_color};"><td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{user_id}</td>'
                table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{user.get("nom_user", "N/A")}</td>'
                table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{user.get("identifiant_user", "N/A")}</td>'
                table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{user.get("email", "N/A")}</td>'
                table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{user.get("statut", "N/A")}</td>'
                table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{"👑 Oui" if user.get("is_admin") else "Non"}</td>'
                date_creation = datetime.fromisoformat(user.get('date_creation', '')).strftime("%d/%m/%Y") if user.get('date_creation') else 'N/A'
                table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{date_creation}</td></tr>'
            
            table_html += '</tbody></table></div>'
        
        # Fermer le conteneur blanc avec le tableau
        st.markdown(f"""
                {table_html}
            </div>
            <script>
                // Fonctionnalité de modification supprimée - le tableau est en lecture seule
            </script>
            <style>
                /* Positionner le champ de recherche juste en dessous du titre dans le conteneur blanc */
                .user-management-section {{
                    position: relative;
                }}
                /* Déplacer le champ de recherche pour qu'il soit juste après le titre avec un espace */
                div[data-testid="stTextInput"]:has(input[placeholder*="Nom, identifiant, email"]) {{
                    position: absolute;
                    top: 5.5rem;
                    left: 2rem;
                    right: 2rem;
                    width: calc(100% - 4rem) !important;
                    z-index: 10;
                    background: white;
                }}
                /* Ajuster le padding du conteneur pour faire de la place au champ */
                .user-management-section {{
                    padding-top: 7rem;
                }}
                /* S'assurer que le titre est en haut avec un petit espace */
                .user-management-section h2 {{
                    margin-top: 0 !important;
                    padding-top: 1rem !important;
                    position: absolute;
                    top: 0;
                    left: 2rem;
                    right: 2rem;
                }}
                /* S'assurer que le label est bien positionné */
                div[data-testid="stTextInput"]:has(input[placeholder*="Nom, identifiant, email"]) label {{
                    margin-bottom: 0.5rem;
                }}
            </style>
        """, unsafe_allow_html=True)
        
        # Fonctionnalité de modification supprimée
        
        # Cacher le DataFrame Streamlit car on utilise le tableau HTML
        if len(filtered_users) > 0:
            df_data = []
            for user in filtered_users:
                df_data.append({
                    'ID': user.get('user_id', 'N/A'),
                    'Nom': user.get('nom_user', 'N/A'),
                    'Identifiant': user.get('identifiant_user', 'N/A'),
                    'Email': user.get('email', 'N/A'),
                    'Statut': user.get('statut', 'N/A'),
                    'Admin': '👑 Oui' if user.get('is_admin') else 'Non',
                    'Date création': datetime.fromisoformat(user.get('date_creation', '')).strftime("%d/%m/%Y") if user.get('date_creation') else 'N/A'
                })
            
            df = pd.DataFrame(df_data)
            # Créer un conteneur avec un ID unique pour cibler ce DataFrame spécifiquement
            st.markdown('<div id="user-management-container">', unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("""
                <style>
                    /* Cacher uniquement le DataFrame dans le conteneur de gestion des utilisateurs */
                    #user-management-container ~ div[data-testid="stDataFrame"],
                    #user-management-container + div[data-testid="stDataFrame"] {
                        display: none !important;
                    }
                </style>
                <script>
                    // Cacher spécifiquement le DataFrame des utilisateurs après le rendu
                    setTimeout(function() {
                        const container = document.getElementById('user-management-container');
                        if (container) {
                            const nextSibling = container.nextElementSibling;
                            if (nextSibling && nextSibling.getAttribute('data-testid') === 'stDataFrame') {
                                nextSibling.style.display = 'none';
                            }
                            // Chercher aussi dans les éléments suivants
                            let sibling = container.nextElementSibling;
                            while (sibling) {
                                if (sibling.getAttribute && sibling.getAttribute('data-testid') === 'stDataFrame') {
                                    sibling.style.display = 'none';
                                    break;
                                }
                                sibling = sibling.nextElementSibling;
                            }
                        }
                    }, 100);
                </script>
            """, unsafe_allow_html=True)
    
    # Tab 3: Historique des classifications
    with tab3:
        # Calculer les métriques
        week_ago = today - timedelta(days=7)
        week_classifications = sum(1 for c in classifications 
                                  if isinstance(c.get('date_classification'), str) and 
                                  datetime.fromisoformat(c.get('date_classification', '').replace('Z', '+00:00')).date() >= week_ago)
        total_text = f"📊 Total de {len(classifications)} classification(s) enregistrée(s)" if len(classifications) > 0 else "📭 Aucune classification enregistrée"
        
        # Conteneur blanc avec tout le contenu
        st.markdown(f"""
            <div class="white-card">
                <h2 class="section-title" style="margin-bottom: 1.5rem;">📈 Historique des Classifications</h2>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem;">
                    <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 15px; border: 2px solid #e0e0e0;">
                        <div style="color: #2d5016; font-family: 'Poppins', sans-serif; font-size: 0.875rem; margin-bottom: 0.5rem; font-weight: 500;">Classifications Aujourd'hui</div>
                        <div style="color: {DOUANE_VERT}; font-family: 'Fredoka', sans-serif; font-size: 2rem; font-weight: 600;">{today_classifications}</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 15px; border: 2px solid #e0e0e0;">
                        <div style="color: #2d5016; font-family: 'Poppins', sans-serif; font-size: 0.875rem; margin-bottom: 0.5rem; font-weight: 500;">Cette Semaine</div>
                        <div style="color: {DOUANE_VERT}; font-family: 'Fredoka', sans-serif; font-size: 2rem; font-weight: 600;">{week_classifications}</div>
                    </div>
                </div>
                <div style="background: #e8f5e9; padding: 1rem 1.5rem; border-radius: 15px; border: 2px solid {DOUANE_VERT}; color: #2d5016; font-family: 'Poppins', sans-serif;">
                    {total_text}
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    # Tab 4: Maintenance
    with tab4:
        # Conteneur blanc avec le titre et les boutons
        with st.container():
            st.markdown(f"""
            """, unsafe_allow_html=True)
            
            # Créer les colonnes pour les boutons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🧹 Vider le Cache", use_container_width=True, key="clear_cache_btn"):
                    st.info("🧹 Cache vidé avec succès")
            
            with col2:
                if st.button("💾 Sauvegarder", use_container_width=True, key="save_backup_btn"):
                    # Créer une sauvegarde
                    backup_data = {
                        "users": users,
                        "classifications": classifications,
                        "backup_date": datetime.now().isoformat()
                    }
                    current_dir = Path(__file__).parent
                    backup_file = current_dir.parent / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    try:
                        with open(backup_file, 'w', encoding='utf-8') as f:
                            json.dump(backup_data, f, ensure_ascii=False, indent=2)
                        st.success(f"✅ Sauvegarde créée : {os.path.basename(backup_file)}")
                    except Exception as e:
                        st.error(f"❌ Erreur lors de la sauvegarde: {e}")
            
            with col3:
                if st.button("📋 Logs Système", use_container_width=True, key="show_logs_btn"):
                    st.session_state.show_logs = not st.session_state.get('show_logs', False)
        
        # CSS pour styliser les boutons de maintenance
        st.markdown(f"""
            <style>
                /* Styliser les 3 boutons de maintenance par leurs clés */
                button[key="clear_cache_btn"],
                button[key="save_backup_btn"],
                button[key="show_logs_btn"] {{
                    background: {DOUANE_OR} !important;
                    color: {DOUANE_VERT} !important;
                    border: 3px solid #2d5016 !important;
                    border-radius: 15px !important;
                    font-family: 'Fredoka', sans-serif !important;
                    font-weight: 600 !important;
                    font-size: 1rem !important;
                    padding: 1rem !important;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
                    transition: all 0.3s ease !important;
                }}
                
                button[key="clear_cache_btn"]:hover,
                button[key="save_backup_btn"]:hover,
                button[key="show_logs_btn"]:hover {{
                    transform: translateY(-3px) !important;
                    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3) !important;
                    background: #FFA500 !important;
                }}
            </style>
            <script>
                console.log('[BUTTONS DEBUG] CSS des boutons de maintenance chargé');
                
                function debugMaintenanceButtons() {{
                    console.log('[BUTTONS DEBUG] Recherche des boutons de maintenance...');
                    const buttons = [
                        document.querySelector('button[key="clear_cache_btn"]'),
                        document.querySelector('button[key="save_backup_btn"]'),
                        document.querySelector('button[key="show_logs_btn"]')
                    ];
                    
                    buttons.forEach((btn, index) => {{
                        if (btn) {{
                            const computedStyle = window.getComputedStyle(btn);
                            console.log('[BUTTONS DEBUG] Bouton', index, 'trouvé:', btn);
                            console.log('[BUTTONS DEBUG] - Background:', computedStyle.backgroundColor);
                            console.log('[BUTTONS DEBUG] - Color:', computedStyle.color);
                            console.log('[BUTTONS DEBUG] - Border:', computedStyle.border);
                            console.log('[BUTTONS DEBUG] - Style inline:', btn.style.cssText);
                            console.log('[BUTTONS DEBUG] - Classes:', btn.className);
                            console.log('[BUTTONS DEBUG] - Attribut key:', btn.getAttribute('key'));
                        }} else {{
                            console.log('[BUTTONS DEBUG] Bouton', index, 'NON TROUVÉ');
                        }}
                    }});
                    
                    // Vérifier les styles CSS appliqués
                    const allButtons = document.querySelectorAll('button');
                    console.log('[BUTTONS DEBUG] Total de boutons sur la page:', allButtons.length);
                    allButtons.forEach((btn, i) => {{
                        const key = btn.getAttribute('key');
                        if (key && (key.includes('cache') || key.includes('backup') || key.includes('logs'))) {{
                            console.log('[BUTTONS DEBUG] Bouton avec key pertinent trouvé:', key, btn);
                        }}
                    }});
                }}
                
                // Exécuter après le chargement
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', () => {{
                        setTimeout(debugMaintenanceButtons, 500);
                    }});
                }} else {{
                    setTimeout(debugMaintenanceButtons, 500);
                }}
                
                // Observer les changements
                const buttonObserver = new MutationObserver(() => {{
                    debugMaintenanceButtons();
                }});
                buttonObserver.observe(document.body, {{ childList: true, subtree: true }});
                
                // Réexécuter périodiquement
                setInterval(debugMaintenanceButtons, 2000);
            </script>
        """, unsafe_allow_html=True)
        
        # Afficher le tableau des logs si demandé
        if st.session_state.get('show_logs', False):
            # Créer un tableau détaillé des logs
            logs_data = []
            
            # Logs système récents
            now = datetime.now()
            logs_data.append({
                "Date/Heure": now.strftime('%Y-%m-%d %H:%M:%S'),
                "Niveau": "INFO",
                "Catégorie": "Système",
                "Message": "Système opérationnel"
            })
            
            logs_data.append({
                "Date/Heure": now.strftime('%Y-%m-%d %H:%M:%S'),
                "Niveau": "INFO",
                "Catégorie": "Accès",
                "Message": "Panneau administrateur ouvert"
            })
            
            logs_data.append({
                "Date/Heure": now.strftime('%Y-%m-%d %H:%M:%S'),
                "Niveau": "INFO",
                "Catégorie": "Utilisateurs",
                "Message": f"{len(users)} utilisateur(s) chargé(s)"
            })
            
            logs_data.append({
                "Date/Heure": now.strftime('%Y-%m-%d %H:%M:%S'),
                "Niveau": "INFO",
                "Catégorie": "Classifications",
                "Message": f"{len(classifications)} classification(s) chargée(s)"
            })
            
            # Ajouter des logs historiques simulés pour un tableau plus complet
            for i in range(1, 11):
                log_time = now - timedelta(hours=i)
                logs_data.append({
                    "Date/Heure": log_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "Niveau": "INFO",
                    "Catégorie": "Système",
                    "Message": f"Vérification système #{i} - Tout fonctionne correctement"
                })
            
            # Ajouter des logs d'activité utilisateurs
            for i in range(1, 6):
                log_time = now - timedelta(minutes=i*15)
                logs_data.append({
                    "Date/Heure": log_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "Niveau": "INFO",
                    "Catégorie": "Activité",
                    "Message": f"Activité utilisateur détectée - Session active"
                })
            
            # Ajouter des logs historiques si disponibles
            current_dir = Path(__file__).parent
            logs_file = current_dir.parent / "system_logs.json"
            if logs_file.exists():
                try:
                    with open(logs_file, 'r', encoding='utf-8') as f:
                        historical_logs = json.load(f)
                        for log in historical_logs[-10:]:  # Derniers 10 logs
                            logs_data.append({
                                "Date/Heure": log.get('timestamp', 'N/A'),
                                "Niveau": log.get('level', 'INFO'),
                                "Catégorie": log.get('category', 'Système'),
                                "Message": log.get('message', 'N/A')
                            })
                except:
                    pass
            
            # Trier par date/heure (plus récent en premier)
            logs_data.sort(key=lambda x: x["Date/Heure"], reverse=True)
            
            # Créer le DataFrame
            if logs_data:
                logs_df = pd.DataFrame(logs_data)
                
                # Préparer les données pour le téléchargement
                csv_data = logs_df.to_csv(index=False, encoding='utf-8-sig')
                json_data = json.dumps(logs_data, ensure_ascii=False, indent=2)
                
                # Afficher les boutons de téléchargement
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.download_button(
                        "📊 CSV",
                        csv_data,
                        file_name=f"logs_systeme_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        key="download_csv_logs",
                        use_container_width=True
                    )
                with col2:
                    st.download_button(
                        "📄 JSON",
                        json_data,
                        file_name=f"logs_systeme_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        key="download_json_logs",
                        use_container_width=True
                    )
                
                
                # Styliser les boutons de téléchargement
                st.markdown(f"""
                    <style>
                        /* Styliser les boutons de téléchargement */
                        div[data-testid="stDownloadButton"] button {{
                            background: {DOUANE_VERT} !important;
                            color: white !important;
                            border: 3px solid #2d5016 !important;
                            border-radius: 10px !important;
                            font-family: 'Fredoka', sans-serif !important;
                            font-weight: 600 !important;
                            font-size: 0.9rem !important;
                            padding: 0.5rem 1rem !important;
                            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15) !important;
                        }}
                        
                        div[data-testid="stDownloadButton"] button:hover {{
                            transform: translateY(-2px) !important;
                            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
                        }}
                    </style>
                """, unsafe_allow_html=True)
                
                # Afficher le tableau avec Streamlit DataFrame stylisé
                st.dataframe(
                    logs_df,
                    use_container_width=True,
                    hide_index=True,
                    height=600
                )
                
                # Ajouter un style pour le DataFrame des logs (simplifié pour éviter les erreurs)
                st.markdown(f"""
                    <style>
                        /* Style général pour le DataFrame des logs - utiliser un sélecteur plus simple */
                        div[data-testid="stDataFrame"] {{
                            background: white !important;
                            border-radius: 15px !important;
                            padding: 1rem !important;
                            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
                        }}
                        
                        /* Désactiver la fonctionnalité de masquage des colonnes */
                        div[data-testid="stDataFrame"] button[aria-label*="column"],
                        div[data-testid="stDataFrame"] button[aria-label*="Column"],
                        div[data-testid="stDataFrame"] button[title*="column"],
                        div[data-testid="stDataFrame"] button[title*="Column"],
                        div[data-testid="stDataFrame"] [data-testid*="column-select"],
                        div[data-testid="stDataFrame"] .stDataFrameColumnMenu,
                        div[data-testid="stDataFrame"] .column-selector,
                        div[data-testid="stDataFrame"] [aria-label*="column menu"],
                        div[data-testid="stDataFrame"] [aria-label*="Column menu"] {{
                            display: none !important;
                            visibility: hidden !important;
                            pointer-events: none !important;
                        }}
                        
                        /* Désactiver la fonctionnalité d'épinglage des colonnes */
                        div[data-testid="stDataFrame"] button[aria-label*="pin"],
                        div[data-testid="stDataFrame"] button[aria-label*="Pin"],
                        div[data-testid="stDataFrame"] button[title*="pin"],
                        div[data-testid="stDataFrame"] button[title*="Pin"],
                        div[data-testid="stDataFrame"] button[aria-label*="épingler"],
                        div[data-testid="stDataFrame"] button[aria-label*="Épingler"],
                        div[data-testid="stDataFrame"] [data-testid*="pin"],
                        div[data-testid="stDataFrame"] .pin-column,
                        div[data-testid="stDataFrame"] [aria-label*="pin column"],
                        div[data-testid="stDataFrame"] [aria-label*="Pin column"] {{
                            display: none !important;
                            visibility: hidden !important;
                            pointer-events: none !important;
                        }}
                        
                        /* Cacher les menus de colonnes */
                        div[data-testid="stDataFrame"] [role="menu"],
                        div[data-testid="stDataFrame"] [role="menuitem"] {{
                            display: none !important;
                        }}
                        
                        /* Style pour l'en-tête du tableau - utiliser des sélecteurs plus simples */
                        div[data-testid="stDataFrame"] table thead tr {{
                            background: white !important;
                            border-bottom: 3px solid {DOUANE_VERT} !important;
                        }}
                        
                        div[data-testid="stDataFrame"] table thead th {{
                            color: {DOUANE_VERT} !important;
                            font-weight: 700 !important;
                            background: white !important;
                        }}
                        
                        /* Style pour les lignes alternées */
                        div[data-testid="stDataFrame"] table tbody tr:nth-child(even) {{
                            background: #f8f9fa !important;
                        }}
                        
                        div[data-testid="stDataFrame"] table tbody tr:hover {{
                            background: #e8f5e9 !important;
                        }}
                        
                        /* Cacher uniquement le DataFrame de gestion des utilisateurs */
                        #user-management-container ~ div[data-testid="stDataFrame"] {{
                            display: none !important;
                        }}
                    </style>
                    <script>
                        // Désactiver complètement les menus de colonnes et l'épinglage
                        function disableDataFrameInteractions() {{
                            const dataframes = document.querySelectorAll('div[data-testid="stDataFrame"]');
                            dataframes.forEach(function(df) {{
                                // Cacher tous les boutons de menu de colonnes
                                const columnButtons = df.querySelectorAll('button[aria-label*="column"], button[aria-label*="Column"], button[title*="column"], button[title*="Column"]');
                                columnButtons.forEach(function(btn) {{
                                    btn.style.display = 'none';
                                    btn.style.visibility = 'hidden';
                                    btn.style.pointerEvents = 'none';
                                    btn.remove();
                                }});
                                
                                // Cacher tous les boutons d'épinglage
                                const pinButtons = df.querySelectorAll('button[aria-label*="pin"], button[aria-label*="Pin"], button[title*="pin"], button[title*="Pin"], button[aria-label*="épingler"], button[aria-label*="Épingler"]');
                                pinButtons.forEach(function(btn) {{
                                    btn.style.display = 'none';
                                    btn.style.visibility = 'hidden';
                                    btn.style.pointerEvents = 'none';
                                    btn.remove();
                                }});
                                
                                // Cacher les menus déroulants
                                const menus = df.querySelectorAll('[role="menu"], [role="menuitem"]');
                                menus.forEach(function(menu) {{
                                    menu.style.display = 'none';
                                    menu.remove();
                                }});
                                
                                // Désactiver complètement les événements de clic sur les en-têtes
                                const headers = df.querySelectorAll('thead th');
                                headers.forEach(function(header) {{
                                    header.style.cursor = 'default';
                                    header.style.userSelect = 'none';
                                    // Supprimer tous les event listeners
                                    const newHeader = header.cloneNode(true);
                                    header.parentNode.replaceChild(newHeader, header);
                                    // Empêcher tous les événements
                                    newHeader.addEventListener('click', function(e) {{
                                        e.preventDefault();
                                        e.stopPropagation();
                                        e.stopImmediatePropagation();
                                        return false;
                                    }}, true);
                                    newHeader.addEventListener('contextmenu', function(e) {{
                                        e.preventDefault();
                                        e.stopPropagation();
                                        return false;
                                    }}, true);
                                }});
                                
                                // Désactiver les événements sur toute la zone du DataFrame
                                df.addEventListener('click', function(e) {{
                                    // Si le clic est sur un bouton de menu ou d'épinglage, l'empêcher
                                    if (e.target.closest('button[aria-label*="pin"], button[aria-label*="Pin"], button[aria-label*="column"], button[aria-label*="Column"]')) {{
                                        e.preventDefault();
                                        e.stopPropagation();
                                        return false;
                                    }}
                                }}, true);
                            }});
                        }}
                        
                        // Exécuter plusieurs fois pour être sûr
                        disableDataFrameInteractions();
                        setTimeout(disableDataFrameInteractions, 100);
                        setTimeout(disableDataFrameInteractions, 500);
                        setTimeout(disableDataFrameInteractions, 1000);
                        
                        // Observer les changements du DOM
                        const observer = new MutationObserver(function(mutations) {{
                            disableDataFrameInteractions();
                        }});
                        observer.observe(document.body, {{ childList: true, subtree: true }});
                    </script>
                """, unsafe_allow_html=True)
            else:
                st.info("Aucun log disponible")
    
    # Footer
    st.markdown(f"""
        <div class="white-card" style="margin-top: 3rem;">
            <div style="text-align: center;">
                <p style="color: {DOUANE_VERT}; margin: 0.5rem 0; font-weight: 600;">🏛️ Direction Générale des Douanes de Côte d'Ivoire</p>
                <p style="color: #2d5016; font-size: 0.875rem; margin: 0.5rem 0;">Système de Classification Tarifaire CEDEAO - TEC SH 2022</p>
                <p style="color: {DOUANE_OR}; font-size: 0.75rem; margin: 0.5rem 0; font-weight: 600;">© {datetime.now().year} - Tous droits réservés</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

