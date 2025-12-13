import streamlit as st
import json
import pandas as pd
from datetime import datetime, timedelta
import os
from pathlib import Path
import html

# Configuration de la page
st.set_page_config(
    page_title="Historique - Classification Tarifaire CEDEAO",
    page_icon="📋",
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
        
        /* Boutons style cartoon */
        .stButton > button {{
            background: {DOUANE_VERT};
            color: white;
            font-family: 'Fredoka', sans-serif;
            font-weight: 600;
            font-size: 1.1rem;
            border: 3px solid #2d5016;
            border-radius: 15px;
            padding: 1rem 2.5rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }}
        
        .stButton > button:hover {{
            transform: translateY(-3px);
            background: #2d7a3d;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
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
            color: {DOUANE_VERT};
            font-family: 'Fredoka', sans-serif;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.1);
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
        
        /* Style pour les messages info/success/error */
        .stAlert {{
            border: 3px solid {DOUANE_VERT} !important;
            border-radius: 15px !important;
        }}
        
        [data-baseweb="notification"] {{
            border: 3px solid {DOUANE_VERT} !important;
            border-radius: 15px !important;
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
    </style>
""", unsafe_allow_html=True)

def load_classification_history():
    """Charge l'historique des classifications depuis le fichier JSON"""
    try:
        # Charger depuis table_data.json
        current_dir = Path(__file__).parent
        table_data_path = current_dir.parent / "table_data.json"
        if table_data_path.exists():
            with open(table_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        return []
    except Exception as e:
        st.error(f"Erreur lors du chargement de l'historique: {e}")
        return []

def format_date(date_str):
    """Formate une date pour l'affichage"""
    try:
        if isinstance(date_str, str):
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            dt = date_str
        return dt.strftime("%d/%m/%Y %H:%M")
    except:
        return "Date inconnue"

def get_status_badge(status):
    """Retourne un badge HTML pour le statut"""
    colors = {
        'valide': DOUANE_VERT,
        'en_attente': DOUANE_OR,
        'rejete': '#e74c3c'
    }
    color = colors.get(status.lower(), '#666')
    return f'<span style="background-color: {color}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;">{status.upper()}</span>'

def main():
    # Header
    st.markdown(f"""
        <div class="main-header">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <h1>📋 Historique des Classifications</h1>
                    <p>Direction Générale des Douanes de Côte d'Ivoire</p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Bouton retour
    if st.button("🏠 Retour au Système", use_container_width=True):
        st.switch_page("app.py")
    
    # Charger l'historique
    history_data = load_classification_history()
    
    # Calculer les statistiques
    total = len(history_data)
    today = datetime.now().date()
    today_count = sum(1 for item in history_data 
                     if isinstance(item.get('date_classification'), str) and 
                     datetime.fromisoformat(item.get('date_classification', '').replace('Z', '+00:00')).date() == today)
    
    week_ago = today - timedelta(days=7)
    week_count = sum(1 for item in history_data 
                    if isinstance(item.get('date_classification'), str) and 
                    datetime.fromisoformat(item.get('date_classification', '').replace('Z', '+00:00')).date() >= week_ago)
    
    valide_count = sum(1 for item in history_data if item.get('statut_validation', '').lower() == 'valide')
    
    # Section Statistiques
    st.markdown(f"""
        <div class="stats-section">
            <h2 class="section-title" style="text-align: center; margin-bottom: 2rem;">
                Statistiques
            </h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem;">
                <div class="stat-card">
                    <div class="stat-number">{total}</div>
                    <p>Total Classifications</p>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{today_count}</div>
                    <p>Aujourd'hui</p>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{week_count}</div>
                    <p>Cette Semaine</p>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{valide_count}</div>
                    <p>Validées</p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Filtres dans une carte blanche
    st.markdown(f"""
        <div style="background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15); margin-bottom: 2rem; border: 3px solid #2d5016;">
            <h2 class="section-title" style="margin-bottom: 1.5rem;">🔍 Filtres de Recherche</h2>
        </div>
        <style>
            /* Forcer le fond blanc pour les colonnes de filtres qui suivent */
            div[data-testid="stVerticalBlock"]:has(+ div[data-testid="stColumns"]) {{
                background: white !important;
            }}
            
            /* Cibler les colonnes qui suivent le titre Filtres */
            div[data-testid="stColumns"] {{
                background: white !important;
                padding: 0 2rem 1.5rem 2rem !important;
                margin: -2rem -2rem 0 -2rem !important;
                border-radius: 0 0 20px 20px !important;
            }}
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        search_term = st.text_input("🔎 Recherche", placeholder="Description, code tarifaire...", key="search_input")
    
    with col2:
        # Extraire les sections depuis les données (structure flexible)
        sections_set = set()
        for item in history_data:
            if isinstance(item, dict):
                # Structure nouvelle: item.get('classification', {}).get('section', {}).get('number')
                section = item.get('section_produit') or \
                         (item.get('classification', {}).get('section', {}).get('number') if isinstance(item.get('classification'), dict) else None) or \
                         (item.get('classification', {}).get('section') if isinstance(item.get('classification'), dict) else None)
                if section:
                    sections_set.add(str(section))
        sections = ['Toutes'] + sorted(sections_set)
        selected_section = st.selectbox("📑 Section", sections, key="section_select")
    
    with col3:
        # Extraire les statuts depuis les données
        statuses_set = set()
        for item in history_data:
            if isinstance(item, dict):
                status = item.get('statut_validation') or item.get('statut')
                if status:
                    statuses_set.add(str(status))
        statuses = ['Tous'] + sorted(statuses_set)
        selected_status = st.selectbox("✅ Statut", statuses, key="status_select")
    
    with col4:
        date_from = st.date_input("📅 Date début", value=None, key="date_from")
        date_to = st.date_input("📅 Date fin", value=None, key="date_to")
    
    # Appliquer les filtres avec structure de données flexible
    filtered_data = history_data.copy()
    
    if search_term:
        filtered_data = [item for item in filtered_data 
                        if isinstance(item, dict) and (
                            search_term.lower() in str(item.get('description_produit', '')).lower() or
                            search_term.lower() in str(item.get('code_tarifaire', '')).lower() or
                            search_term.lower() in str(item.get('product', {}).get('description', '')).lower() or
                            search_term.lower() in str(item.get('classification', {}).get('code', '')).lower()
                        )]
    
    if selected_section != 'Toutes':
        filtered_data = [item for item in filtered_data 
                        if isinstance(item, dict) and (
                            str(item.get('section_produit', '')) == selected_section or
                            str(item.get('classification', {}).get('section', {}).get('number', '')) == selected_section or
                            str(item.get('classification', {}).get('section', '')) == selected_section
                        )]
    
    if selected_status != 'Tous':
        filtered_data = [item for item in filtered_data 
                         if isinstance(item, dict) and (
                             str(item.get('statut_validation', '')).lower() == selected_status.lower() or
                             str(item.get('statut', '')).lower() == selected_status.lower()
                         )]
    
    if date_from:
        filtered_data = [item for item in filtered_data 
                        if isinstance(item, dict) and (
                            (isinstance(item.get('date_classification'), str) and
                             datetime.fromisoformat(item.get('date_classification', '').replace('Z', '+00:00')).date() >= date_from) or
                            (isinstance(item.get('date'), str) and
                             datetime.fromisoformat(item.get('date', '').replace('Z', '+00:00')).date() >= date_from)
                        )]
    
    if date_to:
        filtered_data = [item for item in filtered_data 
                        if isinstance(item, dict) and (
                            (isinstance(item.get('date_classification'), str) and
                             datetime.fromisoformat(item.get('date_classification', '').replace('Z', '+00:00')).date() <= date_to) or
                            (isinstance(item.get('date'), str) and
                             datetime.fromisoformat(item.get('date', '').replace('Z', '+00:00')).date() <= date_to)
                        )]
    
    # Préparer les données pour le tableau avec structure flexible
    df_data = []
    for item in filtered_data:
        if not isinstance(item, dict):
            continue
            
        # Extraire les données selon la structure
        description = item.get('description_produit') or item.get('product', {}).get('description', 'N/A')
        section = item.get('section_produit') or \
                 (item.get('classification', {}).get('section', {}).get('number') if isinstance(item.get('classification'), dict) else None) or \
                 (item.get('classification', {}).get('section') if isinstance(item.get('classification'), dict) else None) or 'N/A'
        code = item.get('code_tarifaire') or item.get('classification', {}).get('code', 'N/A')
        confidence = item.get('classification_confidence') or item.get('classification', {}).get('confidence', 0)
        status = item.get('statut_validation') or item.get('statut', 'N/A')
        date = item.get('date_classification') or item.get('date', '')
        item_id = item.get('id_produit') or item.get('id', 'N/A')
        
        df_data.append({
            'ID': item_id,
            'Description': description,
            'Section': section,
            'Code Tarifaire': code,
            'Confiance IA (%)': f"{confidence * 100:.1f}%" if isinstance(confidence, (int, float)) else 'N/A',
            'Statut': status,
            'Date': format_date(date)
        })
    
    # Préparer le contenu HTML pour le tableau
    table_html = ""
    if len(filtered_data) == 0:
        table_html = '<div style="background: #e8f5e9; padding: 1rem 1.5rem; border-radius: 15px; border: 2px solid ' + DOUANE_VERT + '; color: #2d5016; font-family: \'Poppins\', sans-serif; margin-top: 1.5rem;">📭 Aucun produit classifié trouvé avec ces critères de recherche.</div>'
    else:
        # Créer le tableau HTML
        table_html = '<div style="margin-top: 1.5rem; overflow-x: auto;"><table style="width: 100%; border-collapse: collapse; background: white;"><thead><tr style="background: ' + DOUANE_VERT + '; color: white;">'
        table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">ID</th>'
        table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Description</th>'
        table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Section</th>'
        table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Code Tarifaire</th>'
        table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Confiance IA (%)</th>'
        table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Statut</th>'
        table_html += '<th style="padding: 1rem; text-align: left; font-family: \'Fredoka\', sans-serif; font-weight: 600;">Date</th>'
        table_html += '</tr></thead><tbody>'
        
        for i, item in enumerate(df_data):
            bg_color = '#f5f5f5' if i % 2 == 0 else 'white'
            table_html += f'<tr style="background: {bg_color};"><td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{html.escape(str(item.get("ID", "N/A")))}</td>'
            table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{html.escape(str(item.get("Description", "N/A")))}</td>'
            table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{html.escape(str(item.get("Section", "N/A")))}</td>'
            table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{html.escape(str(item.get("Code Tarifaire", "N/A")))}</td>'
            table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{html.escape(str(item.get("Confiance IA (%)", "N/A")))}</td>'
            table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{html.escape(str(item.get("Statut", "N/A")))}</td>'
            table_html += f'<td style="padding: 0.75rem; border: 1px solid #e0e0e0;">{html.escape(str(item.get("Date", "N/A")))}</td></tr>'
        
        table_html += '</tbody></table></div>'
    
    # Tableau des résultats dans une carte blanche avec le tableau intégré
    st.markdown(f"""
        <div class="white-card">
            <h2 class="section-title" style="margin-bottom: 1.5rem;">📊 Résultats ({len(filtered_data)} classification(s))</h2>
            {table_html}
        </div>
    """, unsafe_allow_html=True)
    
    # Bouton d'export (téléchargement direct)
    if len(filtered_data) > 0:
        df = pd.DataFrame(df_data)
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 Exporter en CSV",
            data=csv,
            file_name=f"historique_classifications_cedeao_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
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

