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
            color: {DOUANE_VERT};
            font-family: 'Fredoka', sans-serif;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.1);
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
    
    # Préserver les query_params importants lors du refresh (comme sur la page principale)
    # Vérifier d'abord session_state (persiste entre pages), puis query_params (persiste après refresh)
    preserve_params = {}
    
    # Vérifier session_state d'abord (priorité)
    if "_table_cleared" in st.session_state:
        preserve_params["table_cleared"] = "true" if st.session_state["_table_cleared"] else None
    elif "table_cleared" in st.query_params:
        preserve_params["table_cleared"] = st.query_params["table_cleared"]
    
    if "_table_product_ids" in st.session_state:
        # Récupérer depuis session_state et mettre dans query_params
        ids_list = st.session_state["_table_product_ids"]
        if ids_list:
            preserve_params["table_product_ids"] = ",".join(map(str, ids_list))
    elif "table_product_ids" in st.query_params:
        preserve_params["table_product_ids"] = st.query_params["table_product_ids"]
        # Stocker aussi dans session_state pour persister entre pages
        ids_param = st.query_params["table_product_ids"]
        if ids_param:
            ids_list = [int(id_str) for id_str in ids_param.split(",") if id_str.strip().isdigit()]
            if ids_list:
                st.session_state["_table_product_ids"] = ids_list
    
    if "user_id" in st.query_params:
        preserve_params["user_id"] = st.query_params["user_id"]
    
    # Réappliquer les paramètres préservés pour qu'ils restent dans l'URL
    for key, value in preserve_params.items():
        if value is not None:
            st.query_params[key] = value
    
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
        
        # Vérifier session_state d'abord (priorité)
        if "_table_cleared" in st.session_state:
            preserve_params["table_cleared"] = "true" if st.session_state["_table_cleared"] else None
        elif "table_cleared" in st.query_params:
            preserve_params["table_cleared"] = st.query_params["table_cleared"]
        
        if "_table_product_ids" in st.session_state:
            # Récupérer depuis session_state et mettre dans query_params (IMPORTANT pour l'URL)
            ids_list = st.session_state["_table_product_ids"]
            if ids_list:
                preserve_params["table_product_ids"] = ",".join(map(str, ids_list))
                print(f"DEBUG Profil retour: IDs récupérés depuis session_state: {ids_list}")
        elif "table_product_ids" in st.query_params:
            preserve_params["table_product_ids"] = st.query_params["table_product_ids"]
        
        if "user_id" in st.query_params:
            preserve_params["user_id"] = st.query_params["user_id"]
        
        # Appliquer les paramètres préservés dans l'URL (CRITIQUE pour que ça reste après refresh)
        for key, value in preserve_params.items():
            if value is not None:  # Ne pas mettre None dans query_params
                st.query_params[key] = value
                print(f"DEBUG Profil retour: Paramètre préservé dans URL: {key}={value}")
        
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

