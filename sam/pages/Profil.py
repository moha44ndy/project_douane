import streamlit as st
from datetime import datetime
from auth_db import (
    get_current_user, logout, update_user, is_authenticated,
    restore_session_from_cookie
)

# Configuration de la page
st.set_page_config(
    page_title="Profil - Classification Tarifaire CEDEAO",
    page_icon="👤",
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
        
        /* Style pour le conteneur utilisateur */
        .user-info-container {{
            background: white !important;
            padding: 1.5rem !important;
            border-radius: 15px !important;
            margin: 1rem 0 !important;
            border: 2px solid {DOUANE_VERT} !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
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
        
        /* Masquer les logos GitHub et Streamlit dans le header */
        .stDeployButton {{
            display: none !important;
            visibility: hidden !important;
        }}
        
        [data-testid="stDecoration"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        
        /* Masquer le bouton Fork GitHub */
        header a[href*="github.com"],
        header a[href*="github.io"],
        header a[title*="Fork"],
        header a[aria-label*="Fork"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        
        /* Masquer les icônes GitHub dans le header */
        header svg[viewBox*="github"],
        header svg[aria-label*="GitHub"] {{
            display: none !important;
            visibility: hidden !important;
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
        
        /* Boutons style cartoon */
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
        
        /* Titres de section style cartoon */
        .section-title {{
            color: {DOUANE_VERT} !important;
            font-family: 'Fredoka', sans-serif;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.1);
        }}
        
        /* Styles pour les titres h3 dans markdown - en blanc pour la page Profil */
        .stMarkdown h3 {{
            color: white !important;
            font-family: 'Fredoka', sans-serif;
            font-weight: 700;
            font-size: 1.5rem;
        }}
        
        /* Styles pour les labels de text_input - en blanc pour la page Profil */
        .stTextInput label {{
            color: white !important;
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
        
        /* Styles pour les titres h4 dans markdown (section mot de passe) */
        .stMarkdown h4 {{
            color: white !important;
            font-family: 'Fredoka', sans-serif;
            font-weight: 700;
            font-size: 1.3rem;
        }}
        
        /* Styles pour le texte markdown normal (paragraphes) - en blanc */
        .stMarkdown p {{
            color: white !important;
        }}
        
        /* Styles pour les labels de text_input dans le formulaire de mot de passe */
        form[data-testid*="modify_profile"] .stTextInput label,
        form[data-testid*="modify_profile"] label {{
            color: white !important;
            font-family: 'Fredoka', sans-serif;
            font-weight: 600;
            font-size: 1.1rem;
        }}
        
        /* Info card */
        .info-card {{
            background: linear-gradient(135deg, {DOUANE_VERT} 0%, #2d5016 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 15px;
            margin-bottom: 1rem;
            border: 3px solid {DOUANE_OR};
        }}
        
        .info-label {{
            font-size: 0.9rem;
            opacity: 0.9;
            margin-bottom: 0.5rem;
        }}
        
        .info-value {{
            font-size: 1.2rem;
            font-weight: 600;
            font-family: 'Fredoka', sans-serif;
        }}
        
        /* Sidebar moderne */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {DOUANE_VERT} 0%, #1a472a 50%, #2d5016 100%) !important;
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
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
        
        /* ============================================
           OPTIMISATIONS RESPONSIVE - PAGE PROFIL
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
            
            /* Section title */
            .section-title {{
                font-size: 1.5rem !important;
                margin-bottom: 1rem !important;
            }}
            
            /* Info cards */
            .info-card {{
                padding: 1rem !important;
                margin-bottom: 0.8rem !important;
            }}
            
            .info-value {{
                font-size: 1rem !important;
            }}
            
            /* Boutons - taille adaptée */
            button, .stButton > button {{
                font-size: 0.9rem !important;
                padding: 0.5rem 1rem !important;
                width: 100% !important;
                box-sizing: border-box !important;
            }}
            
            /* Inputs - largeur complète */
            .stTextInput > div > div > input,
            .stTextArea > div > div > textarea {{
                font-size: 0.9rem !important;
                width: 100% !important;
                padding: 0.8rem 1rem !important;
            }}
            
            /* User info container */
            .user-info-container {{
                padding: 1rem !important;
                margin: 0.8rem 0 !important;
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
            
            .section-title {{
                font-size: 1.2rem !important;
            }}
            
            .info-card {{
                padding: 0.8rem !important;
            }}
            
            .info-value {{
                font-size: 0.9rem !important;
            }}
            
            button, .stButton > button {{
                font-size: 0.85rem !important;
                padding: 0.4rem 0.8rem !important;
                min-height: 40px !important;
            }}
            
            /* Inputs */
            .stTextInput > div > div > input,
            .stTextArea > div > div > textarea {{
                font-size: 0.85rem !important;
                padding: 0.6rem 0.8rem !important;
            }}
            
            .user-info-container {{
                padding: 0.8rem !important;
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
            
            .section-title {{
                font-size: 1rem !important;
            }}
            
            button, .stButton > button {{
                font-size: 0.8rem !important;
                padding: 0.35rem 0.7rem !important;
                min-height: 36px !important;
            }}
        }}
        
        /* Amélioration du touch sur mobile */
        @media (hover: none) and (pointer: coarse) {{
            button, a, [role="button"], .stButton > button {{
                min-height: 44px !important;
                min-width: 44px !important;
            }}
            
            .stTextInput > div > div > input,
            .stTextArea > div > div > textarea {{
                min-height: 44px !important;
            }}
            
            /* Désactiver les effets hover sur mobile */
            .white-card:hover {{
                transform: none !important;
            }}
        }}
    </style>
""", unsafe_allow_html=True)

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
                
                const rect = sidebar.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.left >= 0;
                
                if (isVisible) {{
                    console.log('Fermeture de la sidebar');
                    sidebar.style.setProperty('display', 'none', 'important');
                    sidebar.style.setProperty('transform', 'translateX(-100%)', 'important');
                    sidebar.style.setProperty('visibility', 'hidden', 'important');
                    sidebar.style.setProperty('opacity', '0', 'important');
                }} else {{
                    console.log('Ouverture de la sidebar');
                    sidebar.style.setProperty('display', 'block', 'important');
                    sidebar.style.setProperty('transform', 'translateX(0)', 'important');
                    sidebar.style.setProperty('visibility', 'visible', 'important');
                    sidebar.style.setProperty('opacity', '1', 'important');
                }}
                
                const event = new Event('sidebar-toggle', {{ bubbles: true }});
                sidebar.dispatchEvent(event);
                sidebar.offsetHeight;
            }} else {{
                console.log('Sidebar non trouvée');
            }}
        }}
        
        // Fonction pour créer et attacher le bouton
        function setupSidebarButton() {{
            if (document.getElementById('custom-sidebar-toggle-btn')) {{
                return;
            }}
            
            const btn = document.createElement('button');
            btn.id = 'custom-sidebar-toggle-btn';
            btn.className = 'sidebar-toggle-btn';
            btn.textContent = '☰ Menu';
            btn.title = 'Ouvrir/Fermer le menu';
            btn.type = 'button';
            
            btn.addEventListener('click', function(e) {{
                e.preventDefault();
                e.stopPropagation();
                toggleSidebar();
            }});
            
            document.body.appendChild(btn);
        }}
        
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', setupSidebarButton);
        }} else {{
            setupSidebarButton();
        }}
        
        setTimeout(setupSidebarButton, 100);
        
        const observer = new MutationObserver(function(mutations) {{
            if (!document.getElementById('custom-sidebar-toggle-btn')) {{
                setupSidebarButton();
            }}
        }});
        observer.observe(document.body, {{ childList: true, subtree: true }});
    </script>
""", unsafe_allow_html=True)

def format_date(date_str):
    """Formate une date pour l'affichage"""
    if not date_str:
        return "Non disponible"
    try:
        if isinstance(date_str, str):
            # Essayer différents formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%d/%m/%Y %H:%M')
                except:
                    continue
        return str(date_str)
    except:
        return str(date_str)

def main():
    # Restaurer la session depuis le cookie/query params si nécessaire
    restore_session_from_cookie()
    
    # Vérifier l'authentification
    if not is_authenticated():
        st.switch_page("pages/Login.py")
        return
    
    # Récupérer l'utilisateur actuel
    current_user = get_current_user()
    if not current_user:
        st.error("❌ Impossible de récupérer les informations utilisateur.")
        st.switch_page("pages/Login.py")
        return
    
    # S'assurer que l'identifiant est dans les query params pour la persistance
    if not st.query_params.get('user_id'):
        st.query_params['user_id'] = current_user.get('identifiant_user', '')
    
    # Plus besoin de préserver table_cleared ou table_product_ids - tout est dans la DB maintenant
    # Préserver seulement user_id si nécessaire
    if "user_id" in st.query_params:
        st.query_params["user_id"] = st.query_params["user_id"]
    
    # Afficher les informations de l'utilisateur dans la sidebar
    if current_user:
        # Conteneur avec fond blanc pour les informations utilisateur
        st.sidebar.markdown(f"""
            <div class="user-info-container">
                <h3 style="color: {DOUANE_VERT}; margin-top: 0; margin-bottom: 0.5rem;">👤 {current_user.get('nom_user', 'Utilisateur')}</h3>
                <p style="color: #666; margin: 0.25rem 0; font-size: 0.9rem;">*{current_user.get('email', '')}*</p>
                {"<p style='color: " + DOUANE_OR + "; margin: 0.5rem 0 0 0; font-weight: 600;'>👑 Administrateur</p>" if current_user.get('is_admin') else ""}
            </div>
        """, unsafe_allow_html=True)
        
        if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
            logout()
    
    # Header
    st.markdown(f"""
        <div class="main-header">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <h1>👤 Mon Profil</h1>
                    <p>Direction Générale des Douanes de Côte d'Ivoire</p>
                    <p style="color: {DOUANE_OR}; margin: 0.5rem 0 0 0; font-size: 0.9rem; font-weight: 600;">Gérez vos informations personnelles</p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Bouton retour
    if st.button("🏠 Retour à l'accueil", use_container_width=True):
        # Préserver les query_params importants lors de la navigation
        # Récupérer depuis session_state (priorité) ou query_params (fallback)
        preserve_params = {}
        
        # Plus besoin de préserver table_cleared ou table_product_ids - tout est dans la DB maintenant
        # Préserver seulement user_id si nécessaire
        if "user_id" in st.query_params:
            st.query_params["user_id"] = st.query_params["user_id"]
        
        st.switch_page("app.py")
    
    # Colonnes pour l'affichage
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📋 Informations Personnelles")
        
        # Afficher les informations en lecture seule
        st.markdown(f"""
            <div class="info-card">
                <div class="info-label">👤 Nom complet</div>
                <div class="info-value">{current_user.get('nom_user', 'Non défini')}</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class="info-card">
                <div class="info-label">🆔 Identifiant</div>
                <div class="info-value">{current_user.get('identifiant_user', 'Non défini')}</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class="info-card">
                <div class="info-label">📧 Email</div>
                <div class="info-value">{current_user.get('email', 'Non défini')}</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class="info-card">
                <div class="info-label">👑 Statut</div>
                <div class="info-value">{'Administrateur' if current_user.get('is_admin') else 'Utilisateur'}</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 📊 Informations de Compte")
        
        # Date de création
        date_creation = current_user.get('date_creation', '')
        st.markdown(f"""
            <div class="info-card">
                <div class="info-label">📅 Date de création</div>
                <div class="info-value">{format_date(date_creation)}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Dernière connexion
        derniere_connexion = current_user.get('derniere_connexion', '')
        st.markdown(f"""
            <div class="info-card">
                <div class="info-label">🕐 Dernière connexion</div>
                <div class="info-value">{format_date(derniere_connexion)}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Statut du compte
        statut = current_user.get('statut', 'actif')
        statut_color = '#4CAF50' if statut == 'actif' else '#F44336'
        st.markdown(f"""
            <div class="info-card">
                <div class="info-label">✅ Statut du compte</div>
                <div class="info-value" style="color: {statut_color};">{statut.upper()}</div>
            </div>
        """, unsafe_allow_html=True)
    
    # Formulaire de modification
    st.markdown("#### 🔐 Changer mon mot de passe")
    st.markdown("Contactez un administrateur pour toute autre modification.")
    
    with st.form("modify_profile_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_password = st.text_input(
                "Nouveau mot de passe",
                type="password",
                help="Laissez vide pour ne pas modifier le mot de passe (minimum 6 caractères)"
            )
        
        with col2:
            confirm_password = st.text_input(
                "Confirmer le mot de passe",
                type="password",
                help="Confirmez votre nouveau mot de passe"
            )
        
        submitted = st.form_submit_button("💾 Enregistrer le nouveau mot de passe", use_container_width=True)
        
        if submitted:
            # Validation
            errors = []
            
            if new_password:
                if len(new_password) < 6:
                    errors.append("Le mot de passe doit contenir au moins 6 caractères.")
                elif new_password != confirm_password:
                    errors.append("Les mots de passe ne correspondent pas.")
            else:
                errors.append("Veuillez entrer un nouveau mot de passe.")
            
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                # Récupérer l'ID utilisateur
                user_id = current_user.get('user_id')
                
                # Si user_id n'est pas disponible, essayer de le récupérer depuis la base de données
                if not user_id:
                    from classifications_db import get_current_user_id
                    user_id = get_current_user_id()
                
                # Si toujours pas d'ID, essayer de le récupérer depuis identifiant_user
                if not user_id and current_user.get('identifiant_user'):
                    try:
                        from database import get_db
                        db = get_db()
                        if db.test_connection():
                            query = "SELECT user_id FROM users WHERE identifiant_user = %s AND statut = 'actif' LIMIT 1"
                            result = db.execute_query(query, (current_user.get('identifiant_user'),))
                            if result and len(result) > 0:
                                user_id = result[0]['user_id']
                    except Exception as e:
                        st.error(f"❌ Erreur lors de la récupération de l'ID utilisateur: {e}")
                
                if not user_id:
                    st.error("❌ Impossible de récupérer l'ID utilisateur. Veuillez vous reconnecter.")
                else:
                    # Mettre à jour uniquement le mot de passe
                    success, message = update_user(user_id, password=new_password)
                    
                    if success:
                        st.success(f"✅ {message}")
                        # Recharger la session depuis la base de données
                        try:
                            from database import get_db
                            db = get_db()
                            if db.test_connection():
                                query = "SELECT * FROM users WHERE user_id = %s"
                                updated_user = db.execute_query(query, (user_id,))
                                if updated_user and len(updated_user) > 0:
                                    user = updated_user[0]
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
                        except Exception as e:
                            pass
                        
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")

if __name__ == "__main__":
    main()

