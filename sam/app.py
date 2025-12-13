import json
import os
import csv
import io
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
from rag import initialize_chatbot, process_user_input
from auth import is_authenticated, get_current_user, logout, initialize_default_users

SECTION_RANGES = [
    ("I", range(1, 6)),
    ("II", range(6, 15)),
    ("III", range(15, 16)),
    ("IV", range(16, 25)),
    ("V", range(25, 28)),
    ("VI", range(28, 39)),
    ("VII", range(39, 41)),
    ("VIII", range(41, 44)),
    ("IX", range(44, 47)),
    ("X", range(47, 50)),
    ("XI", range(50, 64)),
    ("XII", range(64, 68)),
    ("XIII", range(68, 71)),
    ("XIV", range(71, 72)),
    ("XV", range(72, 84)),
    ("XVI", range(84, 86)),
    ("XVII", range(86, 90)),
    ("XVIII", range(90, 93)),
    ("XIX", range(93, 94)),
    ("XX", range(94, 97)),
    ("XXI", range(97, 98)),
]

# Configuration des sections et chapitres pour le tableau
SECTION_CONFIG = {
    'I': {'start': 0, 'count': 5, 'chapters': ['01', '02', '03', '04', '05'], 'title': 'Animaux vivants'},
    'II': {'start': 5, 'count': 9, 'chapters': ['06', '07', '08', '09', '10', '11', '12', '13', '14'], 'title': 'Produits du règne végétal'},
    'III': {'start': 14, 'count': 1, 'chapters': ['15'], 'title': 'Graisses et huiles'},
    'IV': {'start': 15, 'count': 9, 'chapters': ['16', '17', '18', '19', '20', '21', '22', '23', '24'], 'title': 'Produits alimentaires'},
    'V': {'start': 24, 'count': 3, 'chapters': ['25', '26', '27'], 'title': 'Produits minéraux'},
    'VI': {'start': 27, 'count': 11, 'chapters': ['28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38'], 'title': 'Produits chimiques'},
    'VII': {'start': 38, 'count': 2, 'chapters': ['39', '40'], 'title': 'Matières plastiques'},
    'VIII': {'start': 40, 'count': 3, 'chapters': ['41', '42', '43'], 'title': 'Cuirs et peaux'},
    'IX': {'start': 43, 'count': 3, 'chapters': ['44', '45', '46'], 'title': 'Bois et ouvrages'},
    'X': {'start': 46, 'count': 3, 'chapters': ['47', '48', '49'], 'title': 'Pâtes de bois'},
    'XI': {'start': 49, 'count': 14, 'chapters': ['50', '51', '52', '53', '54', '55', '56', '57', '58', '59', '60', '61', '62', '63'], 'title': 'Textiles'},
    'XII': {'start': 63, 'count': 4, 'chapters': ['64', '65', '66', '67'], 'title': 'Chaussures'},
    'XIII': {'start': 67, 'count': 3, 'chapters': ['68', '69', '70'], 'title': 'Ouvrages en pierre'},
    'XIV': {'start': 70, 'count': 1, 'chapters': ['71'], 'title': 'Perles'},
    'XV': {'start': 71, 'count': 11, 'chapters': ['72', '73', '74', '75', '76', '78', '79', '80', '81', '82', '83'], 'title': 'Métaux'},
    'XVI': {'start': 84, 'count': 2, 'chapters': ['84', '85'], 'title': 'Machines'},
    'XVII': {'start': 86, 'count': 4, 'chapters': ['86', '87', '88', '89'], 'title': 'Matériel de transport'},
    'XVIII': {'start': 90, 'count': 3, 'chapters': ['90', '91', '92'], 'title': 'Instruments'},
    'XIX': {'start': 93, 'count': 1, 'chapters': ['93'], 'title': 'Armes'},
    'XX': {'start': 94, 'count': 3, 'chapters': ['94', '95', '96'], 'title': 'Divers'},
    'XXI': {'start': 97, 'count': 1, 'chapters': ['97'], 'title': 'Objets d\'art'},
}


def extract_chapter_from_code(code: str | None) -> str | None:
    if not code:
        return None
    digits = "".join(ch for ch in code if ch.isdigit())
    if len(digits) >= 2:
        return digits[:2]
    return None


def infer_section_from_chapter(chapter_code: str | None) -> str | None:
    if not chapter_code:
        return None
    try:
        value = int(chapter_code)
    except ValueError:
        return None
    for section_name, chapter_range in SECTION_RANGES:
        if value in chapter_range:
            return section_name
    return None


def parse_structured_response(raw_text: str | None) -> tuple[dict | None, str | None]:
    if not raw_text:
        return None, "Réponse vide"
    try:
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            return None, "Format inattendu (objet JSON attendu)"
        data.setdefault("narrative", "")
        data.setdefault("classifications", [])
        return data, None
    except json.JSONDecodeError as exc:
        return None, f"Impossible de parser la réponse JSON ({exc})"


def format_response_markdown(payload: dict) -> str:
    sections = []
    narrative = (payload.get("narrative") or "").strip()
    if narrative:
        sections.append(narrative)

    for idx, item in enumerate(payload.get("classifications", []), start=1):
        description = item.get("description") or "Marchandise non précisée"
        hs_code = item.get("hs_code") or "Non renseigné"
        chapter = (item.get("chapter") or "N/A")
        section = item.get("section") or infer_section_from_chapter(chapter) or "N/A"
        dd_rate = item.get("dd_rate") or "Non renseigné"
        rs_rate = item.get("rs_rate") or "Non renseigné"
        other_taxes = item.get("other_taxes") or "Non renseigné"
        us_unit = item.get("us_unit") or "Non renseigné"
        justification = item.get("justification") or "Justification non fournie"
        excerpt = item.get("excerpt") or ""

        block = [
            f"**Marchandise {idx} – {description}**",
            f"- Position TEC/SH : {hs_code} (Chapitre {chapter}, Section {section})",
            f"- Taux : D.D. {dd_rate} ; R.S. {rs_rate} ; Autres taxes {other_taxes} ; U.S. {us_unit}",
            f"- Justification : {justification}",
        ]
        if excerpt:
            block.append(f"- Extrait : {excerpt}")
        sections.append("\n".join(block))

    return "\n\n".join(sections) if sections else "Aucune donnée structurée reçue."




def build_table_entries(classifications: list) -> list:
    """Construit les entrées pour le tableau à partir des classifications"""
    entries = []
    for item in classifications:
        description = item.get("description", "N/A")
        hs_code = item.get("hs_code", "N/A")
        chapter = item.get("chapter") or extract_chapter_from_code(hs_code) or "N/A"
        section = item.get("section") or infer_section_from_chapter(chapter) or "N/A"
        
        entry = {
            "product": {
                "description": description,
                "value": item.get("value", "N/A"),
                "origin": item.get("origin", "N/A"),
            },
            "classification": {
                "code": hs_code,
                "section": {"number": section},
                "confidence": item.get("confidence", 0),
            }
        }
        entries.append(entry)
    return entries


def generate_csv_download():
    """Génère un fichier CSV téléchargeable"""
    table_data = st.session_state.get("table_products", [])
    if not table_data:
        return None
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Description", "Section", "Chapitre", "Code TEC/SH", "Confiance", "Valeur", "Origine"])
    
    for entry in table_data:
        product = entry.get("product", {})
        classification = entry.get("classification", {})
        section = classification.get("section", {}).get("number", "N/A")
        code = classification.get("code", "N/A")
        chapter = extract_chapter_from_code(code) or "N/A"
        
        writer.writerow([
            product.get("description", "N/A"),
            section,
            chapter,
            code,
            classification.get("confidence", 0),
            product.get("value", "N/A"),
            product.get("origin", "N/A"),
        ])
    
    return output.getvalue()


def generate_json_download():
    """Génère un fichier JSON téléchargeable"""
    table_data = st.session_state.get("table_products", [])
    if not table_data:
        return None
    
    export_data = {
        "export_date": datetime.now().isoformat(),
        "total_products": len(table_data),
        "products": []
    }
    
    for entry in table_data:
        product = entry.get("product", {})
        classification = entry.get("classification", {})
        section = classification.get("section", {}).get("number", "N/A")
        code = classification.get("code", "N/A")
        chapter = extract_chapter_from_code(code) or "N/A"
        
        export_data["products"].append({
            "description": product.get("description", "N/A"),
            "section": section,
            "chapter": chapter,
            "hs_code": code,
            "confidence": classification.get("confidence", 0),
            "value": product.get("value", "N/A"),
            "origin": product.get("origin", "N/A"),
        })
    
    return json.dumps(export_data, ensure_ascii=False, indent=2)


# Fonctions pour le tableau
def load_table_data():
    """Charge les données du tableau depuis la session state ou le fichier"""
    if "table_products" in st.session_state:
        return st.session_state["table_products"]
    
    current_dir = Path(__file__).parent
    table_data_path = current_dir / "table_data.json"
    try:
        if table_data_path.exists():
            with open(table_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data = data if isinstance(data, list) else []
                st.session_state["table_products"] = data
                return data
    except Exception as e:
        st.error(f"Erreur lors du chargement: {e}")
    return []

def save_table_data(data):
    """Sauvegarde les données du tableau"""
    st.session_state["table_products"] = data
    current_dir = Path(__file__).parent
    table_data_path = current_dir / "table_data.json"
    try:
        with open(table_data_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde: {e}")
        return False

def get_products_by_chapter(table_data):
    """Organise les produits par chapitre"""
    products_by_chapter = {}
    for item in table_data:
        if isinstance(item, dict) and 'product' in item and 'classification' in item:
            classification = item.get('classification', {})
            code = classification.get('code', 'N/A')
            chapter = extract_chapter_from_code(code) or 'N/A'
            product_info = item.get('product', {})
            description = product_info.get('description', 'N/A')
            value = product_info.get('value', 0)
            confidence = classification.get('confidence', 0)
        else:
            chapter = item.get('chapter', 'N/A')
            description = item.get('description', 'N/A')
            value = item.get('value', 0)
            confidence = item.get('confidence', 0)
            code = item.get('code', 'N/A')
        
        if chapter not in products_by_chapter:
            products_by_chapter[chapter] = []
        products_by_chapter[chapter].append({
            'description': description,
            'code': code,
            'value': value,
            'confidence': confidence
        })
    return products_by_chapter

def render_table_grid():
    """Affiche la grille du tableau avec sections et chapitres"""
    table_data = load_table_data()
    products_by_chapter = get_products_by_chapter(table_data)
    
    # CSS pour le tableau
    st.markdown(f"""
        <style>
            .table-container {{
                overflow-x: auto;
                border: 2px solid {DOUANE_VERT};
                border-radius: 8px;
                background: white;
                margin: 1rem 0;
            }}
            .section-header {{
                background: {DOUANE_VERT};
                color: white;
                font-weight: bold;
                text-align: center;
                padding: 10px 5px;
                font-size: 11px;
                border-right: 2px solid #2E7D32;
            }}
            .chapter-cell {{
                background: #E8F5E8;
                border: 1px solid {DOUANE_VERT};
                padding: 8px;
                text-align: center;
                font-size: 10px;
                min-width: 80px;
            }}
            .product-cell {{
                background: {DOUANE_OR};
                border: 1px solid {DOUANE_VERT};
                padding: 5px;
                font-size: 9px;
                min-width: 80px;
                min-height: 60px;
            }}
            .product-cell.empty {{
                background: white;
            }}
            .chapter-number {{
                font-weight: bold;
                color: {DOUANE_VERT};
                font-size: 12px;
            }}
            .product-info {{
                font-size: 8px;
                color: {DOUANE_VERT};
            }}
            .stats-badge {{
                background: {DOUANE_OR};
                color: {DOUANE_VERT};
                padding: 2px 6px;
                border-radius: 10px;
                font-size: 9px;
                font-weight: bold;
                margin-top: 4px;
            }}
        </style>
    """, unsafe_allow_html=True)
    
    # Construire le HTML du tableau
    html_table = '<div class="table-container"><table style="width: 100%; border-collapse: collapse; min-width: 4500px;">'
    
    # Ligne d'en-têtes des sections
    html_table += '<tr>'
    for section, config in SECTION_CONFIG.items():
        colspan = config['count']
        html_table += f'<td class="section-header" colspan="{colspan}">'
        html_table += f'<div style="font-size: 12px; margin-bottom: 3px;">Section {section}</div>'
        html_table += f'<div style="font-size: 9px; opacity: 0.9;">{config["title"]}</div>'
        html_table += f'<div class="stats-badge" id="stats-{section}">0</div>'
        html_table += '</td>'
    html_table += '</tr>'
    
    # Ligne des numéros de chapitres
    html_table += '<tr>'
    for section, config in SECTION_CONFIG.items():
        for chapter in config['chapters']:
            count = len(products_by_chapter.get(chapter, []))
            html_table += f'<td class="chapter-cell">'
            html_table += f'<div class="chapter-number">Ch. {chapter}</div>'
            html_table += f'<div class="stats-badge" id="chap-stats-{chapter}">{count}</div>'
            html_table += '</td>'
    html_table += '</tr>'
    
    # Lignes de produits (maximum 20 lignes)
    max_rows = max(1, max([len(products_by_chapter.get(ch, [])) for ch in products_by_chapter.keys()] + [1]))
    max_rows = min(max_rows, 20)  # Limiter à 20 lignes
    
    for row_idx in range(max_rows):
        html_table += '<tr>'
        for section, config in SECTION_CONFIG.items():
            for chapter in config['chapters']:
                products = products_by_chapter.get(chapter, [])
                if row_idx < len(products):
                    product = products[row_idx]
                    html_table += f'<td class="product-cell">'
                    html_table += f'<div class="product-info"><strong>{product["code"]}</strong></div>'
                    html_table += f'<div class="product-info">{product["description"][:15]}...</div>'
                    html_table += f'<div class="product-info">{product["value"]} FCFA</div>'
                    html_table += '</td>'
                else:
                    html_table += '<td class="product-cell empty"></td>'
        html_table += '</tr>'
    
    html_table += '</table></div>'
    
    # Mettre à jour les statistiques des sections
    section_stats = {}
    for section, config in SECTION_CONFIG.items():
        count = 0
        for chapter in config['chapters']:
            count += len(products_by_chapter.get(chapter, []))
        section_stats[section] = count
    
    # JavaScript pour mettre à jour les stats
    stats_script = '<script>'
    for section, count in section_stats.items():
        stats_script += f'document.getElementById("stats-{section}").textContent = "{count}";'
    stats_script += '</script>'
    
    st.markdown(html_table + stats_script, unsafe_allow_html=True)

def export_table_to_csv():
    """Exporte les données en CSV"""
    table_data = load_table_data()
    if not table_data:
        return None
    
    df_data = []
    for item in table_data:
        if isinstance(item, dict) and 'product' in item and 'classification' in item:
            product_info = item.get('product', {})
            classification = item.get('classification', {})
            section = classification.get('section', {})
            if isinstance(section, dict):
                section = section.get('number', 'N/A')
            else:
                section = section or 'N/A'
            code = classification.get('code', 'N/A')
            chapter = extract_chapter_from_code(code) or 'N/A'
            description = product_info.get('description', 'N/A')
            value = product_info.get('value', 0)
            confidence = classification.get('confidence', 0)
            origin = product_info.get('origin', 'N/A')
            timestamp = item.get('timestamp', datetime.now().isoformat())
        else:
            description = item.get('description', 'N/A')
            section = item.get('section', 'N/A')
            chapter = item.get('chapter', 'N/A')
            code = item.get('code', 'N/A')
            value = item.get('value', 0)
            confidence = item.get('confidence', 0)
            origin = item.get('origin', 'N/A')
            timestamp = item.get('timestamp', datetime.now().isoformat())
        
        df_data.append({
            'Description': description,
            'Section': section,
            'Chapitre': chapter,
            'Code Tarifaire': code,
            'Confiance (%)': confidence * 100 if isinstance(confidence, (int, float)) else 0,
            'Valeur (FCFA)': value,
            'Origine': origin,
            'Date': timestamp
        })
    
    df = pd.DataFrame(df_data)
    return df.to_csv(index=False, encoding='utf-8-sig')

def export_table_to_json():
    """Exporte les données en JSON"""
    table_data = load_table_data()
    if not table_data:
        return None
    
    export_data = {
        'export_date': datetime.now().isoformat(),
        'total_products': len(table_data),
        'products': table_data
    }
    
    return json.dumps(export_data, ensure_ascii=False, indent=2)

def clear_table_data():
    """Vide toutes les données du tableau"""
    save_table_data([])
    st.success("✅ Tableau vidé avec succès")
    st.rerun()

def view_table_statistics():
    """Affiche les statistiques détaillées"""
    table_data = load_table_data()
    if not table_data:
        st.info("📭 Aucune donnée à afficher")
        return
    
    products_by_chapter = get_products_by_chapter(table_data)
    
    st.markdown("### 📊 Statistiques Détaillées")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Par Section")
        section_stats = {}
        for section, config in SECTION_CONFIG.items():
            count = sum(len(products_by_chapter.get(ch, [])) for ch in config['chapters'])
            section_stats[section] = count
        
        stats_df = pd.DataFrame([
            {'Section': sec, 'Produits': count, 'Titre': SECTION_CONFIG[sec]['title']}
            for sec, count in sorted(section_stats.items())
        ])
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
    
    with col2:
        st.markdown("#### Top 10 Chapitres")
        chapter_counts = [(ch, len(products_by_chapter.get(ch, []))) for ch in products_by_chapter.keys()]
        chapter_counts.sort(key=lambda x: x[1], reverse=True)
        
        if chapter_counts:
            top_df = pd.DataFrame([
                {'Chapitre': ch, 'Produits': count}
                for ch, count in chapter_counts[:10]
            ])
            st.dataframe(top_df, use_container_width=True, hide_index=True)

def render_table_component():
    """Affiche le composant tableau en Streamlit"""
    st.markdown("### 📋 Système Harmonisé Complet (21 Sections - 97 Chapitres)")
    
    # Boutons de contrôle
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🗑️ Vider le tableau", use_container_width=True):
            if st.session_state.get('confirm_clear', False):
                clear_table_data()
                st.session_state.confirm_clear = False
            else:
                st.session_state.confirm_clear = True
                st.warning("⚠️ Cliquez à nouveau pour confirmer la suppression")
    
    with col2:
        csv_data = export_table_to_csv()
        if csv_data:
            st.download_button(
                "📊 Exporter CSV",
                csv_data,
                file_name=f"tableau_classification_cedeao_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.button("📊 Exporter CSV", disabled=True, use_container_width=True)
    
    with col3:
        json_data = export_table_to_json()
        if json_data:
            st.download_button(
                "📄 Exporter JSON",
                json_data,
                file_name=f"tableau_classification_cedeao_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )
        else:
            st.button("📄 Exporter JSON", disabled=True, use_container_width=True)
    
    with col4:
        table_data = load_table_data()
        total = len(table_data)
        st.metric("📈 Total Produits", total)
    
    # Afficher la grille du tableau
    render_table_grid()
    
    # Bouton pour voir les statistiques
    if st.button("📈 Voir statistiques", use_container_width=True):
        view_table_statistics()

# Configuration de la page
st.set_page_config(
    page_title="Mosam - Classification Tarifaire CEDEAO",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Couleurs du thème
DOUANE_VERT = "#1B5E20"
DOUANE_OR = "#FFD700"
DOUANE_BLANC = "#FFFFFF"
# Les pages Streamlit sont accessibles via le système de pages intégré
# Plus besoin d'URLs externes - Streamlit gère automatiquement les routes

# CSS style militaire/cartoon inspiré du design Dribbble
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
        
        /* Afficher tous les boutons du header Streamlit */
        .stDeployButton {{
            display: block !important;
        }}
        
        [data-testid="stToolbar"] {{
            display: flex !important;
        }}
        
        [data-testid="stDecoration"] {{
            display: block !important;
        }}
        
        /* Afficher tous les boutons du header */
        header button {{
            display: block !important;
            visibility: visible !important;
        }}
        
        /* Afficher le bouton sidebar natif */
        button[kind="header"] {{
            display: block !important;
            visibility: visible !important;
        }}
        
        /* Style pour le header Streamlit */
        header[data-testid="stHeader"] {{
            background: white !important;
            border-bottom: 3px solid {DOUANE_VERT} !important;
            padding: 0.5rem 1rem !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
        }}
        
        /* Bouton sidebar personnalisé dans le header */
        .header-sidebar-btn {{
            background: {DOUANE_OR} !important;
            color: {DOUANE_VERT} !important;
            border: 3px solid #2d5016 !important;
            border-radius: 12px !important;
            padding: 0.5rem 1rem !important;
            font-family: 'Fredoka', sans-serif !important;
            font-weight: 600 !important;
            font-size: 0.9rem !important;
            cursor: pointer !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
            transition: all 0.3s ease !important;
            margin-left: 1rem !important;
        }}
        
        .header-sidebar-btn:hover {{
            transform: translateY(-2px) !important;
            background: #FFA500 !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        }}
        
        /* Style pour le conteneur du header */
        header[data-testid="stHeader"] > div {{
            display: flex !important;
            align-items: center !important;
            justify-content: space-between !important;
            width: 100% !important;
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
        
        /* Boutons de navigation style cartoon */
        .header-link-button {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: {DOUANE_OR};
            color: {DOUANE_VERT};
            font-family: 'Fredoka', sans-serif;
            font-weight: 600;
            font-size: 1rem;
            border: 3px solid #2d5016;
            border-radius: 15px;
            padding: 0.75rem 1.5rem;
            text-decoration: none !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            position: relative;
        }}
        
        .header-link-button:hover {{
            transform: translateY(-3px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
            background: #FFA500;
        }}
        
        .header-link-button:active {{
            transform: translateY(-1px);
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
        
        /* Formulaire style cartoon */
        .form-card {{
            background: white;
            padding: 2rem;
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            margin-bottom: 2rem;
            border: 4px solid #2d5016;
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
        
        /* Bouton Envoyer style cartoon */
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
        
        .stButton > button:active {{
            transform: translateY(-1px);
        }}
        
        /* Messages de chat style cartoon */
        .chat-card {{
            background: white;
            padding: 2rem;
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            margin-bottom: 2rem;
            border: 4px solid #2d5016;
        }}
        
        .user-message {{
            background: {DOUANE_OR};
            color: {DOUANE_VERT};
            padding: 1.25rem 1.75rem;
            border-radius: 20px;
            border: 3px solid #2d5016;
            margin-bottom: 1rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            transition: all 0.3s ease;
            font-family: 'Poppins', sans-serif;
            font-weight: 500;
            animation: slideInRight 0.5s ease-out;
        }}
        
        @keyframes slideInRight {{
            from {{
                opacity: 0;
                transform: translateX(30px);
            }}
            to {{
                opacity: 1;
                transform: translateX(0);
            }}
        }}
        
        .user-message:hover {{
            transform: translateX(5px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
        }}
        
        .rag-message {{
            background: {DOUANE_VERT};
            color: white;
            padding: 1.25rem 1.75rem;
            border-radius: 20px;
            border: 3px solid #2d5016;
            margin-bottom: 1rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            transition: all 0.3s ease;
            font-family: 'Poppins', sans-serif;
            font-weight: 500;
            animation: slideInLeft 0.5s ease-out;
        }}
        
        @keyframes slideInLeft {{
            from {{
                opacity: 0;
                transform: translateX(-30px);
            }}
            to {{
                opacity: 1;
                transform: translateX(0);
            }}
        }}
        
        .rag-message:hover {{
            transform: translateX(-5px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
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
        
        /* Bulle de dialogue style cartoon */
        .speech-bubble {{
            background: white;
            padding: 1.5rem 2rem;
            border-radius: 25px;
            border: 4px solid #2d5016;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
            position: relative;
            margin: 1rem 0;
            font-family: 'Fredoka', sans-serif;
            font-size: 1.2rem;
            font-weight: 600;
            color: {DOUANE_VERT};
        }}
        
        .speech-bubble::after {{
            content: '';
            position: absolute;
            bottom: -20px;
            left: 50px;
            width: 0;
            height: 0;
            border-left: 20px solid transparent;
            border-right: 20px solid transparent;
            border-top: 20px solid white;
        }}
        
        .speech-bubble::before {{
            content: '';
            position: absolute;
            bottom: -24px;
            left: 48px;
            width: 0;
            height: 0;
            border-left: 22px solid transparent;
            border-right: 22px solid transparent;
            border-top: 22px solid #2d5016;
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
        
        @keyframes fadeInDown {{
            from {{
                opacity: 0;
                transform: translateY(-30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        /* Sidebar moderne */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {DOUANE_VERT} 0%, #1a472a 50%, #1a1a2e 100%) !important;
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
        }}
        
        /* Effet de particules subtil en arrière-plan (statique) */
        .stApp::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: 
                radial-gradient(circle at 20% 50%, rgba(255, 215, 0, 0.05) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(27, 94, 32, 0.05) 0%, transparent 50%),
                radial-gradient(circle at 40% 20%, rgba(255, 140, 0, 0.03) 0%, transparent 50%);
            pointer-events: none;
            z-index: 0;
            opacity: 0.6;
        }}
        
        .main .block-container {{
            position: relative;
            z-index: 1;
        }}
        
        /* Bouton Effacer l'historique */
        .stButton > button:has-text("Effacer") {{
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
            font-weight: 700;
            border: none;
            border-radius: 0.75rem;
            padding: 0.875rem 2rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 8px 25px rgba(239, 68, 68, 0.4);
        }}
        
        .stButton > button:has-text("Effacer"):hover {{
            transform: translateY(-3px) scale(1.02);
            box-shadow: 0 12px 35px rgba(239, 68, 68, 0.6);
            background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
        }}
        
        /* Amélioration générale des boutons - mais ne pas bloquer les styles spécifiques */
        button:not(.stButton > button):not([data-baseweb="button"]) {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
        }}
        
        /* Animation pour les éléments qui apparaissent */
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.8; }}
        }}
        
        .stat-card:hover .stat-number {{
            animation: pulse 1s ease-in-out infinite;
        }}
    </style>
""", unsafe_allow_html=True)

# Initialize chatbot
if "initialized" not in st.session_state:
    chunks, emb, index = initialize_chatbot()
    st.session_state["chunks"] = chunks
    st.session_state["emb"] = emb
    st.session_state["index"] = index
    st.session_state["initialized"] = True

# Initialize table products
if "table_products" not in st.session_state:
    st.session_state["table_products"] = load_table_data()

def display_main_content():
    """Affiche le contenu principal avec le nouveau design"""
    
    # Ajouter le bouton dans le header Streamlit
    st.markdown(f"""
        <script>
            function addSidebarButtonToHeader() {{
                // Attendre que le header soit chargé
                const header = document.querySelector('header[data-testid="stHeader"]');
                if (header) {{
                    // Vérifier si le bouton existe déjà
                    if (document.getElementById('custom-sidebar-btn')) {{
                        return;
                    }}
                    
                    // Créer le bouton
                    const btn = document.createElement('button');
                    btn.id = 'custom-sidebar-btn';
                    btn.className = 'header-sidebar-btn';
                    btn.innerHTML = '☰ Menu';
                    btn.title = 'Ouvrir/Fermer le menu';
                    btn.onclick = function() {{
                        toggleSidebar();
                    }};
                    
                    // Trouver le conteneur du header et ajouter le bouton
                    const headerContainer = header.querySelector('div');
                    if (headerContainer) {{
                        // Ajouter le bouton au début du conteneur
                        headerContainer.insertBefore(btn, headerContainer.firstChild);
                    }} else {{
                        header.appendChild(btn);
                    }}
                }} else {{
                    // Réessayer après un court délai
                    setTimeout(addSidebarButtonToHeader, 100);
                }}
            }}
            
            function toggleSidebar() {{
                // Chercher le bouton natif de Streamlit pour ouvrir/fermer la sidebar
                const sidebarButton = document.querySelector('button[kind="header"]');
                if (sidebarButton) {{
                    sidebarButton.click();
                }} else {{
                    // Alternative: chercher par data-testid
                    const altButton = document.querySelector('[data-testid="baseButton-header"]');
                    if (altButton) {{
                        altButton.click();
                    }} else {{
                        // Forcer l'affichage/masquage de la sidebar
                        const sidebar = document.querySelector('[data-testid="stSidebar"]');
                        if (sidebar) {{
                            const isVisible = sidebar.style.display !== 'none' && 
                                            sidebar.style.visibility !== 'hidden';
                            if (isVisible) {{
                                sidebar.style.display = 'none';
                                sidebar.style.transform = 'translateX(-100%)';
                                sidebar.style.visibility = 'hidden';
                            }} else {{
                                sidebar.style.display = 'block';
                                sidebar.style.transform = 'translateX(0)';
                                sidebar.style.visibility = 'visible';
                            }}
                        }}
                    }}
                }}
            }}
            
            // Exécuter au chargement de la page
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', addSidebarButtonToHeader);
            }} else {{
                addSidebarButtonToHeader();
            }}
            
            // Réessayer après un court délai pour s'assurer que le header est chargé
            setTimeout(addSidebarButtonToHeader, 500);
            
            // Observer les changements du DOM pour s'assurer que le bouton reste
            const observer = new MutationObserver(function(mutations) {{
                const btn = document.getElementById('custom-sidebar-btn');
                if (!btn) {{
                    addSidebarButtonToHeader();
                }}
            }});
            observer.observe(document.body, {{ childList: true, subtree: true }});
        </script>
    """, unsafe_allow_html=True)
    
    # Header style cartoon avec bulle de dialogue
    st.markdown(f"""
        <div style="position: relative; margin-bottom: 2rem;">
            <div class="speech-bubble" style="margin-bottom: 1rem;">
                🏛️ Bienvenue dans Mosam - Classification Tarifaire CEDEAO
            </div>
            <div class="main-header">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                    <div>
                        <h1>Direction Générale des Douanes</h1>
                        <p>TEC SH 2022 - Côte d'Ivoire</p>
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Section Statistiques style cartoon
    st.markdown(f"""
        <div class="stats-section">
            <h2 class="section-title" style="text-align: center; margin-bottom: 2rem;">
                Statistiques du Système
            </h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem;">
                <div class="stat-card">
                    <div style="
                        font-family: 'Fredoka', sans-serif;
                        font-size: 3rem; 
                        font-weight: 700; 
                        color: {DOUANE_VERT}; 
                        margin-bottom: 0.5rem;
                        text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.1);
                    ">21</div>
                    <div style="
                        font-family: 'Poppins', sans-serif;
                        font-size: 1.1rem; 
                        color: {DOUANE_VERT}; 
                        font-weight: 600;
                    ">Sections</div>
                </div>
                <div class="stat-card">
                    <div style="
                        font-family: 'Fredoka', sans-serif;
                        font-size: 3rem; 
                        font-weight: 700; 
                        color: {DOUANE_VERT}; 
                        margin-bottom: 0.5rem;
                        text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.1);
                    ">97</div>
                    <div style="
                        font-family: 'Poppins', sans-serif;
                        font-size: 1.1rem; 
                        color: {DOUANE_VERT}; 
                        font-weight: 600;
                    ">Chapitres</div>
                </div>
                <div class="stat-card">
                    <div style="
                        font-family: 'Fredoka', sans-serif;
                        font-size: 3rem; 
                        font-weight: 700; 
                        color: {DOUANE_VERT}; 
                        margin-bottom: 0.5rem;
                        text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.1);
                    ">5000+</div>
                    <div style="
                        font-family: 'Poppins', sans-serif;
                        font-size: 1.1rem; 
                        color: {DOUANE_VERT}; 
                        font-weight: 600;
                    ">Codes tarifaires</div>
                </div>
                <div class="stat-card">
                    <div style="
                        font-family: 'Fredoka', sans-serif;
                        font-size: 3rem; 
                        font-weight: 700; 
                        color: {DOUANE_VERT}; 
                        margin-bottom: 0.5rem;
                        text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.1);
                    ">2022</div>
                    <div style="
                        font-family: 'Poppins', sans-serif;
                        font-size: 1.1rem; 
                        color: {DOUANE_VERT}; 
                        font-weight: 600;
                    ">Version SH</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state for chat history
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    
    # Formulaire dans une carte blanche
    st.markdown("""
        <div class="form-card">
            <h3 class="section-title">✍️ Posez votre question</h3>
        </div>
    """, unsafe_allow_html=True)
    
    with st.form("chat_form", clear_on_submit=True):
        user_message = st.text_input("Votre question:", placeholder="Ex: Comment classifier un produit électronique?")
        submitted = st.form_submit_button("🚀 Envoyer", use_container_width=True)

    # Traitement du message
    if submitted and user_message:
        spinner_placeholder = st.empty()
        with spinner_placeholder.container():
            st.markdown("""
                <div style="
                    background: linear-gradient(135deg, #FF8C00 0%, #B8860B 100%);
                    color: white;
                    padding: 1rem;
                    border-radius: 0.5rem;
                    text-align: center;
                    margin: 1rem 0;
                    box-shadow: 0 4px 15px rgba(255, 140, 0, 0.3);
                ">
                    <div style="display: flex; align-items: center; justify-content: center; gap: 1rem;">
                        <div style="
                            border: 3px solid rgba(255, 255, 255, 0.3);
                            border-top: 3px solid white;
                            border-radius: 50%;
                            width: 24px;
                            height: 24px;
                            animation: spin 1s linear infinite;
                        "></div>
                        <span style="font-weight: bold; font-size: 1.1rem;">🤔 Mosam réfléchit...</span>
                    </div>
                </div>
                <style>
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
            """, unsafe_allow_html=True)
        
        # Réinitialiser l'historique pour n'afficher que la requête en cours
        st.session_state["messages"] = []
        st.session_state["messages"].append(("Vous", user_message))
        response = process_user_input(
            user_message, 
            st.session_state["chunks"], 
            st.session_state["emb"], 
            st.session_state["index"], 
        )

        parsed_payload, parse_error = parse_structured_response(response)
        if parsed_payload:
            formatted_answer = format_response_markdown(parsed_payload)
            st.session_state["messages"].append(("RAG", formatted_answer))
            new_entries = build_table_entries(parsed_payload.get("classifications", []))
            if new_entries:
                st.session_state["table_products"].extend(new_entries)
                save_table_data(st.session_state.get("table_products", []))
        else:
            fallback_text = response or f"⚠️ {parse_error}"
            st.session_state["messages"].append(("RAG", fallback_text))

        spinner_placeholder.empty()
        st.rerun()
    
    # Zone de chat dans une carte blanche
    if st.session_state["messages"]:
        st.markdown("""
            <div class="chat-card">
                <h3 class="section-title">💬 Historique de la conversation</h3>
        """, unsafe_allow_html=True)
        
        # Afficher les messages style cartoon
        for i in range(0, len(st.session_state["messages"]), 2):
            if i < len(st.session_state["messages"]):
                user, user_message = st.session_state["messages"][i]
                st.markdown(f"""
                    <div class="user-message">
                        <strong style="font-size: 1.1rem; font-weight: 700; display: block; margin-bottom: 0.5rem;">👤 Vous</strong>
                        <div style="line-height: 1.6; font-size: 1rem;">{user_message}</div>
                    </div>
                """, unsafe_allow_html=True)
            
            if i + 1 < len(st.session_state["messages"]):
                rag, rag_message = st.session_state["messages"][i + 1]
                st.markdown(f"""
                    <div class="rag-message">
                        <strong style="font-size: 1.1rem; font-weight: 700; display: block; margin-bottom: 0.5rem;">🤖 Mosam</strong>
                        <div style="line-height: 1.6; font-size: 1rem;">{rag_message}</div>
                    </div>
                """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Bouton pour effacer l'historique avec style moderne
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🗑️ Effacer l'historique", use_container_width=True):
                st.session_state["messages"] = []
                st.rerun()
    
    # Afficher le nombre de produits classés avec style moderne
    product_count = len(st.session_state.get("table_products", []))
    if product_count > 0:
        st.markdown(f"""
            <div style="
                background: white;
                padding: 1rem 1.5rem;
                border-radius: 15px;
                border: 3px solid {DOUANE_VERT};
                margin: 1rem 0;
                display: inline-flex;
                align-items: center;
                gap: 0.75rem;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            ">
                <span style="font-size: 2rem;">📊</span>
                <span style="
                    font-family: 'Fredoka', sans-serif;
                    color: {DOUANE_VERT}; 
                    font-weight: 700; 
                    font-size: 1.2rem;
                ">
                    {product_count} produit(s) classé(s) dans le tableau
                </span>
            </div>
        """, unsafe_allow_html=True)
    
    render_table_component()

def main():
    # Initialiser les utilisateurs par défaut si nécessaire
    initialize_default_users()
    
    # Vérifier l'authentification
    if not is_authenticated():
        st.switch_page("pages/Login.py")
        return
    
    # Afficher les informations de l'utilisateur dans la sidebar
    current_user = get_current_user()
    if current_user:
        with st.sidebar:
            st.markdown("---")
            st.markdown(f"### 👤 {current_user.get('nom_user', 'Utilisateur')}")
            st.markdown(f"*{current_user.get('email', '')}*")
            if current_user.get('is_admin'):
                st.markdown("👑 **Administrateur**")
                if st.button("🛡️ Administration", use_container_width=True):
                    st.switch_page("pages/Administration.py")
            if st.button("🚪 Déconnexion", use_container_width=True):
                logout()
    
    display_main_content()

if __name__ == "__main__":
    main()
