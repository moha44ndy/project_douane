import json
import os
import csv
import io
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
from rag import initialize_chatbot, process_user_input
from auth_db import is_authenticated, get_current_user, logout, initialize_default_users
from classifications_db import load_table_data, save_table_data

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

# Noms des chapitres du Système Harmonisé
CHAPTER_NAMES = {
    '01': 'Animaux vivants', '02': 'Viandes et abats comestibles', '03': 'Poissons et crustacés',
    '04': 'Lait et produits laitiers', '05': 'Autres produits d\'origine animale',
    '06': 'Arbres et plantes vivantes', '07': 'Légumes', '08': 'Fruits', '09': 'Café, thé, épices',
    '10': 'Céréales', '11': 'Produits de la meunerie', '12': 'Graines et fruits oléagineux',
    '13': 'Gommes et résines', '14': 'Matières végétales', '15': 'Graisses et huiles',
    '16': 'Préparations de viande', '17': 'Sucres', '18': 'Cacao', '19': 'Préparations à base de céréales',
    '20': 'Préparations de légumes', '21': 'Préparations alimentaires', '22': 'Boissons',
    '23': 'Résidus alimentaires', '24': 'Tabac',
    '25': 'Sel, soufre, terres', '26': 'Minerais', '27': 'Combustibles',
    '28': 'Produits chimiques inorganiques', '29': 'Produits chimiques organiques',
    '30': 'Produits pharmaceutiques', '31': 'Engrais', '32': 'Extraits tannants',
    '33': 'Huiles essentielles', '34': 'Savons et détergents', '35': 'Matières albuminoïdes',
    '36': 'Explosifs', '37': 'Produits photographiques', '38': 'Produits chimiques divers',
    '39': 'Matières plastiques', '40': 'Caoutchouc',
    '41': 'Cuirs et peaux', '42': 'Articles de maroquinerie', '43': 'Fourrures',
    '44': 'Bois', '45': 'Liège', '46': 'Ouvrages en sparterie',
    '47': 'Pâtes de bois', '48': 'Papiers', '49': 'Imprimés',
    '50': 'Soie', '51': 'Laine', '52': 'Coton', '53': 'Fibres textiles',
    '54': 'Filaments synthétiques', '55': 'Fibres synthétiques', '56': 'Ouates',
    '57': 'Tapis', '58': 'Tissus spéciaux', '59': 'Tissus imprégnés',
    '60': 'Tricots', '61': 'Vêtements tricotés', '62': 'Vêtements confectionnés',
    '63': 'Autres articles textiles',
    '64': 'Chaussures', '65': 'Coiffures', '66': 'Parapluies', '67': 'Plumes',
    '68': 'Ouvrages en pierre', '69': 'Céramiques', '70': 'Verre',
    '71': 'Perles et pierres précieuses',
    '72': 'Fonte et fer', '73': 'Ouvrages en fonte', '74': 'Cuivre',
    '75': 'Nickel', '76': 'Aluminium', '78': 'Plomb', '79': 'Zinc',
    '80': 'Étain', '81': 'Autres métaux', '82': 'Outils', '83': 'Ouvrages divers',
    '84': 'Machines', '85': 'Appareils électriques',
    '86': 'Voies ferrées', '87': 'Véhicules', '88': 'Aéronefs', '89': 'Navires',
    '90': 'Instruments', '91': 'Horlogerie', '92': 'Instruments de musique',
    '93': 'Armes', '94': 'Ameublement', '95': 'Jouets', '96': 'Articles divers',
    '77': 'Réservé', '97': 'Objets d\'art'
}

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
    classifications = payload.get("classifications", [])
    
    # Si plusieurs classifications, ajouter un message informatif au tout début (juste après "🤖 Mosam")
    if len(classifications) > 1:
        sections.append('<span style="color: red;">💡 **Plusieurs classifications possibles détectées.** Veuillez refaire une classification en précisant davantage votre produit en utilisant les informations disponibles dans la réponse ci-dessous.</span>\n')
    
    narrative = (payload.get("narrative") or "").strip()
    if narrative:
        sections.append(narrative)

    for idx, item in enumerate(classifications, start=1):
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
                "justification": item.get("justification") or None,
                "taux_dd": item.get("dd_rate") or None,
                "taux_rs": item.get("rs_rate") or None,
                "taux_tva": item.get("other_taxes") or None,
                "unite_mesure": item.get("us_unit") or None,
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


# Fonctions pour le tableau - Utilisation de MySQL via classifications_db
# (import déjà fait en haut du fichier, ligne 11)

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
        
        # Ignorer les produits avec chapitre 'N/A' ou code invalide
        if chapter == 'N/A' or not code or code == 'N/A':
            continue
        
        # Normaliser le chapitre en string à 2 chiffres (ex: "84" au lieu de 84)
        if chapter and chapter != 'N/A':
            chapter = str(chapter).zfill(2) if len(str(chapter)) == 1 else str(chapter)
        
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
    # Utiliser les données du tableau local (session_state) au lieu de recharger depuis la base
    # Cela permet de respecter le vidage intentionnel du tableau
    table_data = st.session_state.get("table_products", [])
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
                padding: 6px 4px;
                text-align: center;
                font-size: 10px;
                min-width: 100px;
                vertical-align: top;
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
                font-size: 11px;
                margin-bottom: 3px;
            }}
            .chapter-name {{
                font-size: 7px;
                color: #555;
                margin-top: 2px;
                line-height: 1.1;
                font-weight: normal;
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
    
    # Ligne des numéros de chapitres avec leurs noms
    html_table += '<tr>'
    for section, config in SECTION_CONFIG.items():
        for chapter in config['chapters']:
            count = len(products_by_chapter.get(chapter, []))
            chapter_name = CHAPTER_NAMES.get(chapter, '')
            html_table += f'<td class="chapter-cell">'
            html_table += f'<div class="chapter-number">Ch. {chapter}</div>'
            if chapter_name:
                # Tronquer le nom si trop long
                display_name = chapter_name[:25] + '...' if len(chapter_name) > 25 else chapter_name
                html_table += f'<div class="chapter-name" title="{chapter_name}">{display_name}</div>'
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
            # S'assurer que le chapitre est bien formaté comme string à 2 chiffres
            chapter_str = str(chapter).zfill(2) if chapter else None
            if chapter_str:
                count += len(products_by_chapter.get(chapter_str, []))
        section_stats[section] = count
    
    # Mettre à jour directement dans le HTML au lieu d'utiliser JavaScript
    # Remplacer les badges de stats dans le HTML
    for section, count in section_stats.items():
        # Remplacer le badge de stats dans le HTML
        old_badge = f'<div class="stats-badge" id="stats-{section}">0</div>'
        new_badge = f'<div class="stats-badge" id="stats-{section}">{count}</div>'
        html_table = html_table.replace(old_badge, new_badge)
    
    st.markdown(html_table, unsafe_allow_html=True)

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
    """Vide toutes les données du tableau local (session_state) sans supprimer les données de la base"""
    # Ne vider que le tableau local, pas la base de données
    # Cela permet de conserver les statistiques dans la page Historique
    try:
        st.session_state["table_products"] = []
        # Marquer que le tableau a été vidé intentionnellement (dans session_state ET query_params pour persister)
        st.session_state["_table_cleared"] = True
        st.query_params["table_cleared"] = "true"  # Persister dans l'URL pour survivre au refresh
        # Supprimer les IDs du tableau dans session_state et query_params
        if "_table_product_ids" in st.session_state:
            del st.session_state["_table_product_ids"]
        if "table_product_ids" in st.query_params:
            del st.query_params["table_product_ids"]
        
        # Sauvegarder la préférence dans la base de données pour persister après déconnexion
        try:
            from classifications_db import get_current_user_id
            from database import get_db
            user_id = get_current_user_id()
            if user_id:
                db = get_db()
                if db.test_connection():
                    try:
                        from database import _get_db_type
                        is_postgresql = (_get_db_type() == 'postgresql')
                    except:
                        is_postgresql = False
                    
                    # Vérifier si la colonne existe, sinon la créer
                    try:
                        if is_postgresql:
                            # Vérifier si la colonne existe
                            check_query = """
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name='users' AND column_name='table_cleared'
                            """
                            result = db.execute_query(check_query)
                            if not result:
                                # Créer la colonne
                                db.execute_update("ALTER TABLE users ADD COLUMN table_cleared BOOLEAN DEFAULT FALSE", ())
                        else:
                            # MySQL
                            check_query = """
                            SELECT COLUMN_NAME 
                            FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'users' 
                            AND COLUMN_NAME = 'table_cleared'
                            """
                            result = db.execute_query(check_query)
                            if not result:
                                # Créer la colonne
                                db.execute_update("ALTER TABLE users ADD COLUMN table_cleared BOOLEAN DEFAULT FALSE", ())
                    except Exception as e:
                        # La colonne existe peut-être déjà, continuer
                        print(f"Note: table_cleared column check: {e}")
                    
                    # Mettre à jour la préférence de l'utilisateur
                    try:
                        update_query = "UPDATE users SET table_cleared = %s WHERE user_id = %s"
                        db.execute_update(update_query, (True, user_id))
                    except Exception as e:
                        # Si la colonne n'existe pas, essayer de la créer d'abord
                        print(f"Erreur lors de la mise à jour, tentative de création de colonne: {e}")
                        try:
                            db.execute_update("ALTER TABLE users ADD COLUMN table_cleared BOOLEAN DEFAULT FALSE", ())
                            db.execute_update(update_query, (True, user_id))
                        except Exception as e2:
                            print(f"Erreur lors de la création de la colonne: {e2}")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la préférence table_cleared: {e}")
            # Continuer quand même - le tableau est vidé localement
        
        st.success("✅ Tableau vidé avec succès (les données restent dans l'historique)")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Erreur lors du vidage du tableau: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

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
                try:
                    clear_table_data()
                    st.session_state.confirm_clear = False
                except Exception as e:
                    st.error(f"❌ Erreur lors du vidage: {e}")
                    import traceback
                    st.code(traceback.format_exc())
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
        # Afficher le total depuis le tableau local, pas depuis la base
        table_data = st.session_state.get("table_products", [])
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
    layout="wide",  # "wide" pour desktop, mais optimisé pour mobile via CSS
    initial_sidebar_state="expanded"
)

# Couleurs du thème
DOUANE_VERT = "#1B5E20"
DOUANE_OR = "#FFD700"
DOUANE_BLANC = "#FFFFFF"
# Les pages Streamlit sont accessibles via le système de pages intégré
# Plus besoin d'URLs externes - Streamlit gère automatiquement les routes

# CSS style militaire/cartoon inspiré du design Dribbble
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
        
        /* Style pour les boutons de notation */
        div[data-testid="column"] button[kind="secondary"] {{
            font-size: 1.5rem !important;
            padding: 0.5rem 1rem !important;
            border-radius: 10px !important;
            transition: all 0.3s ease !important;
            border: 2px solid !important;
        }}
        
        div[data-testid="column"] button[kind="secondary"]:hover {{
            transform: scale(1.1) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
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
        
        /* ============================================
           OPTIMISATIONS MOBILE
           ============================================ */
        
        @media screen and (max-width: 768px) {{
            /* Conteneur principal - padding réduit sur mobile */
            .main .block-container {{
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                padding-top: 0.5rem !important;
            }}
            
            /* Cartes blanches - padding réduit */
            .white-card {{
                padding: 1rem !important;
                margin-bottom: 1rem !important;
                border-radius: 15px !important;
            }}
            
            /* Header - taille réduite */
            .main-header {{
                padding: 1rem !important;
                margin-bottom: 1rem !important;
            }}
            
            .main-header h1 {{
                font-size: 1.5rem !important;
            }}
            
            /* Tableau - défilement horizontal optimisé */
            .table-container {{
                overflow-x: auto !important;
                -webkit-overflow-scrolling: touch !important;
            }}
            
            .table-container table {{
                min-width: 4500px !important;
                font-size: 0.7rem !important;
            }}
            
            /* Boutons - taille adaptée */
            button {{
                font-size: 0.85rem !important;
                padding: 0.4rem 0.8rem !important;
            }}
            
            /* Formulaire - largeur complète */
            .stTextInput > div > div > input {{
                font-size: 0.9rem !important;
            }}
            
            /* Messages de chat - padding réduit */
            .chat-message {{
                padding: 0.8rem !important;
                margin-bottom: 0.8rem !important;
            }}
            
            /* Sidebar - optimisée pour mobile */
            [data-testid="stSidebar"] {{
                min-width: 200px !important;
            }}
            
            /* Boutons de feedback - colonnes empilées sur mobile */
            /* Cibler les colonnes Streamlit pour les empiler sur mobile */
            [data-testid="column"] {{
                min-width: auto !important;
                width: 100% !important;
                margin-bottom: 0.5rem !important;
            }}
            
            /* Forcer les colonnes à être empilées verticalement */
            [data-testid="stHorizontalBlock"] {{
                flex-direction: column !important;
            }}
            
            /* Statistiques - colonnes empilées */
            .stat-card {{
                margin-bottom: 1rem !important;
            }}
            
            /* Header Streamlit - hauteur réduite */
            header[data-testid="stHeader"] {{
                padding: 0.3rem 0.5rem !important;
            }}
            
            .header-sidebar-btn {{
                font-size: 0.75rem !important;
                padding: 0.3rem 0.6rem !important;
                margin-left: 0.5rem !important;
            }}
        }}
        
        @media screen and (max-width: 480px) {{
            /* Très petits écrans - optimisations supplémentaires */
            .main .block-container {{
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
            }}
            
            .white-card {{
                padding: 0.8rem !important;
                border-radius: 12px !important;
            }}
            
            .main-header h1 {{
                font-size: 1.2rem !important;
            }}
            
            .table-container table {{
                font-size: 0.6rem !important;
            }}
            
            button {{
                font-size: 0.75rem !important;
                padding: 0.3rem 0.6rem !important;
            }}
            
            /* Colonnes Streamlit - empilées sur très petit écran */
            .element-container {{
                width: 100% !important;
            }}
        }}
        
        /* Amélioration du touch sur mobile */
        @media (hover: none) and (pointer: coarse) {{
            button, a, [role="button"] {{
                min-height: 44px !important;
                min-width: 44px !important;
            }}
            
            /* Désactiver les effets hover sur mobile */
            .white-card:hover {{
                transform: none !important;
            }}
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
# Ne charger depuis la base que si le tableau n'a pas été vidé intentionnellement
# Vérifier à la fois session_state, query_params ET la base de données pour persister après déconnexion
table_cleared_session = st.session_state.get("_table_cleared", False) or st.query_params.get("table_cleared") == "true"

# NOTE: table_cleared_db sera récupéré plus tard, après l'authentification de l'utilisateur
# pour s'assurer que get_current_user_id() retourne une valeur valide
table_cleared_db = False

# CRITIQUE: Préserver les query_params importants dès le chargement de la page
# Récupérer depuis session_state (priorité) et mettre dans query_params pour l'URL
# Cela garantit que les IDs restent dans l'URL même après un retour depuis une autre page
if "_table_product_ids" in st.session_state:
    ids_list = st.session_state["_table_product_ids"]
    if ids_list:
        ids_str = ",".join(map(str, ids_list))
        # Mettre dans query_params seulement si ce n'est pas déjà présent ou différent
        if st.query_params.get("table_product_ids") != ids_str:
            st.query_params["table_product_ids"] = ids_str
            print(f"DEBUG app.py global init: IDs récupérés depuis session_state et mis dans query_params: {ids_list}")

if "_table_cleared" in st.session_state:
    cleared_value = "true" if st.session_state["_table_cleared"] else None
    if st.query_params.get("table_cleared") != cleared_value:
        if cleared_value is not None:
            st.query_params["table_cleared"] = cleared_value
            print(f"DEBUG app.py global init: table_cleared récupéré depuis session_state et mis dans query_params: {cleared_value}")

# Initialiser le tableau
# Logique : Ne vider le tableau que si le flag est True ET que le tableau n'a pas de données
if "table_products" not in st.session_state:
    # Première initialisation - vérifier les préférences
    # PRIORITÉ: Vérifier d'abord query_params (persiste après refresh), puis DB, puis session_state
    table_cleared_from_url = st.query_params.get("table_cleared") == "true"
    
    # Si le tableau a été vidé, charger seulement les produits dont les IDs sont stockés dans query_params
    if table_cleared_db or table_cleared_from_url or table_cleared_session:
        # Le tableau a été vidé intentionnellement
        # Charger seulement les produits dont les IDs sont stockés dans query_params
        print(f"DEBUG: Tableau vidé - chargement des produits par IDs - table_cleared_db={table_cleared_db}, table_cleared_from_url={table_cleared_from_url}, table_cleared_session={table_cleared_session}")
        try:
            from classifications_db import load_classifications_by_ids, get_current_user_id
            user_id = get_current_user_id()
            if user_id:
                # Récupérer les IDs depuis session_state (priorité) ou query_params (fallback)
                classification_ids = None
                if "_table_product_ids" in st.session_state:
                    classification_ids = st.session_state["_table_product_ids"]
                    print(f"DEBUG: IDs récupérés depuis session_state: {classification_ids}")
                else:
                    ids_param = st.query_params.get("table_product_ids", "")
                    if ids_param:
                        classification_ids = [int(id_str) for id_str in ids_param.split(",") if id_str.strip().isdigit()]
                        # Stocker aussi dans session_state pour persister entre pages
                        if classification_ids:
                            st.session_state["_table_product_ids"] = classification_ids
                            print(f"DEBUG: IDs récupérés depuis query_params et stockés dans session_state: {classification_ids}")
                
                if classification_ids:
                    # Charger seulement les produits avec ces IDs
                    loaded_data = load_classifications_by_ids(classification_ids, user_id)
                    st.session_state["table_products"] = loaded_data
                    print(f"DEBUG: {len(loaded_data)} produit(s) chargé(s) par IDs: {classification_ids}")
                else:
                    st.session_state["table_products"] = []
                    print(f"DEBUG: Aucun ID trouvé dans session_state ni query_params")
            else:
                st.session_state["table_products"] = []
        except Exception as e:
            print(f"DEBUG: Erreur lors du chargement des produits par IDs: {e}")
            st.session_state["table_products"] = []
        
        st.session_state["_table_cleared"] = True
        # Garder le flag dans query_params pour persister après refresh
        st.query_params["table_cleared"] = "true"
        # S'assurer que le flag est aussi dans la DB
        if not table_cleared_db:
            try:
                from classifications_db import get_current_user_id
                from database import get_db
                user_id = get_current_user_id()
                if user_id:
                    db = get_db()
                    if db.test_connection():
                        update_query = "UPDATE users SET table_cleared = %s WHERE user_id = %s"
                        db.execute_update(update_query, (True, user_id))
                        print(f"DEBUG: Flag table_cleared mis à jour dans la DB")
            except Exception as e:
                print(f"DEBUG: Erreur lors de la mise à jour de table_cleared dans la DB: {e}")
    else:
        # Le tableau n'a pas été vidé - charger les données depuis la base
        print(f"DEBUG: Tableau initialisé avec données depuis la base")
        loaded_data = load_table_data()
        st.session_state["table_products"] = loaded_data
        st.session_state["_table_cleared"] = False
        
        # Stocker les IDs dans session_state (persiste entre pages) et query_params (persiste après refresh)
        current_ids = [e.get('id') for e in loaded_data if e.get('id')]
        if current_ids:
            st.session_state["_table_product_ids"] = current_ids
            st.query_params["table_product_ids"] = ",".join(map(str, current_ids))
            print(f"DEBUG: IDs du tableau stockés dans session_state et query_params: {current_ids}")
else:
    # Le tableau existe déjà dans session_state
    # Vérifier d'abord si le flag table_cleared est actif (priorité ABSOLUE sur le contenu du tableau)
    # Re-vérifier query_params et DB car session_state peut être réinitialisé après refresh
    table_cleared_from_url = st.query_params.get("table_cleared") == "true"
    table_cleared_from_session = st.session_state.get("_table_cleared", False)
    
    # PRIORITÉ: Si le flag est actif dans query_params OU DB, charger seulement les produits dont les IDs sont stockés
    if table_cleared_db or table_cleared_from_url:
        # Le flag est actif (DB ou URL) - charger seulement les produits dont les IDs sont stockés dans query_params
        print(f"DEBUG: Flag table_cleared actif (DB={table_cleared_db}, URL={table_cleared_from_url}) - chargement des produits par IDs")
        try:
            from classifications_db import load_classifications_by_ids, get_current_user_id
            user_id = get_current_user_id()
            if user_id:
                # Récupérer les IDs depuis session_state (priorité) ou query_params (fallback)
                classification_ids = None
                if "_table_product_ids" in st.session_state:
                    classification_ids = st.session_state["_table_product_ids"]
                    print(f"DEBUG: IDs récupérés depuis session_state: {classification_ids}")
                else:
                    ids_param = st.query_params.get("table_product_ids", "")
                    if ids_param:
                        classification_ids = [int(id_str) for id_str in ids_param.split(",") if id_str.strip().isdigit()]
                        # Stocker aussi dans session_state pour persister entre pages
                        if classification_ids:
                            st.session_state["_table_product_ids"] = classification_ids
                            print(f"DEBUG: IDs récupérés depuis query_params et stockés dans session_state: {classification_ids}")
                
                if classification_ids:
                    # Charger seulement les produits avec ces IDs
                    loaded_data = load_classifications_by_ids(classification_ids, user_id)
                    st.session_state["table_products"] = loaded_data
                    print(f"DEBUG: {len(loaded_data)} produit(s) chargé(s) par IDs: {classification_ids}")
                else:
                    # Si pas d'IDs trouvés, garder le tableau tel quel
                    pass
            else:
                # Si pas d'utilisateur, garder le tableau tel quel
                pass
        except Exception as e:
            print(f"DEBUG: Erreur lors du chargement des produits par IDs: {e}")
        
        # S'assurer que le flag est bien défini partout
        st.session_state["_table_cleared"] = True
        st.query_params["table_cleared"] = "true"
        # S'assurer que le flag est aussi dans la DB
        if not table_cleared_db:
            try:
                from classifications_db import get_current_user_id
                from database import get_db
                user_id = get_current_user_id()
                if user_id:
                    db = get_db()
                    if db.test_connection():
                        update_query = "UPDATE users SET table_cleared = %s WHERE user_id = %s"
                        db.execute_update(update_query, (True, user_id))
                        print(f"DEBUG: Flag table_cleared mis à jour dans la DB")
            except Exception as e:
                print(f"DEBUG: Erreur lors de la mise à jour de table_cleared dans la DB: {e}")
    elif table_cleared_from_session:
        # Le flag est actif seulement dans session_state (mais pas dans DB/URL)
        # Cela peut arriver si l'utilisateur vient de vider le tableau
        # S'assurer que le flag est aussi dans query_params et DB pour persister
        print(f"DEBUG: Flag table_cleared actif seulement dans session_state - synchronisation avec URL et DB")
        st.session_state["_table_cleared"] = True
        st.query_params["table_cleared"] = "true"
        try:
            from classifications_db import get_current_user_id
            from database import get_db
            user_id = get_current_user_id()
            if user_id:
                db = get_db()
                if db.test_connection():
                    update_query = "UPDATE users SET table_cleared = %s WHERE user_id = %s"
                    db.execute_update(update_query, (True, user_id))
                    print(f"DEBUG: Flag table_cleared synchronisé avec DB")
        except Exception as e:
            print(f"DEBUG: Erreur lors de la synchronisation de table_cleared: {e}")
    else:
        # Le flag n'est PAS actif - vérifier si le tableau contient des données
        current_table = st.session_state.get("table_products", [])
        
        # Vérifier si des IDs sont disponibles dans query_params ou session_state (retour depuis autre page après refresh)
        # Même si le tableau contient des données, vérifier les IDs pour s'assurer qu'ils sont synchronisés
        classification_ids = None
        if "_table_product_ids" in st.session_state:
            classification_ids = st.session_state["_table_product_ids"]
        else:
            ids_param = st.query_params.get("table_product_ids", "")
            if ids_param:
                classification_ids = [int(id_str) for id_str in ids_param.split(",") if id_str.strip().isdigit()]
                # Stocker aussi dans session_state pour persister entre pages
                if classification_ids:
                    st.session_state["_table_product_ids"] = classification_ids
                    print(f"DEBUG: IDs récupérés depuis query_params et stockés dans session_state: {classification_ids}")
        
        # Si le tableau est vide mais que des IDs sont disponibles, recharger depuis les IDs
        if not current_table and classification_ids:
            print(f"DEBUG: Tableau vide mais IDs disponibles - rechargement depuis les IDs (retour depuis autre page)")
            try:
                from classifications_db import load_classifications_by_ids, get_current_user_id
                user_id = get_current_user_id()
                if user_id:
                    loaded_data = load_classifications_by_ids(classification_ids, user_id)
                    st.session_state["table_products"] = loaded_data
                    current_table = loaded_data
                    print(f"DEBUG: {len(loaded_data)} produit(s) rechargé(s) depuis les IDs: {classification_ids}")
            except Exception as e:
                print(f"DEBUG: Erreur lors du rechargement depuis les IDs: {e}")
        
        if current_table:
            # Le tableau contient des données ET le flag n'est pas actif
            # Cela signifie que le tableau n'a jamais été vidé ou a été réinitialisé
            # Ne pas modifier le flag, juste s'assurer qu'il est à False
            if st.session_state.get("_table_cleared", False):
                st.session_state["_table_cleared"] = False
            if "table_cleared" in st.query_params:
                del st.query_params["table_cleared"]
            
            # S'assurer que les IDs sont synchronisés dans session_state et query_params
            current_ids = [e.get('id') for e in current_table if e.get('id')]
            if current_ids:
                st.session_state["_table_product_ids"] = current_ids
                st.query_params["table_product_ids"] = ",".join(map(str, current_ids))
                print(f"DEBUG: IDs synchronisés dans session_state et query_params: {current_ids}")
            
            # S'assurer que le flag est aussi à False dans la DB
            if table_cleared_db:
                try:
                    from classifications_db import get_current_user_id
                    from database import get_db
                    user_id = get_current_user_id()
                    if user_id:
                        db = get_db()
                        if db.test_connection():
                            try:
                                update_query = "UPDATE users SET table_cleared = %s WHERE user_id = %s"
                                db.execute_update(update_query, (False, user_id))
                                print(f"DEBUG: Flag table_cleared réinitialisé à False dans la DB")
                            except Exception as e:
                                print(f"Note: Erreur lors de la réinitialisation de table_cleared: {e}")
                except Exception as e:
                    print(f"Note: Erreur lors de la vérification de table_cleared: {e}")
        else:
            # Le tableau est vide ET le flag n'est pas actif
            # Vérifier si des IDs sont disponibles dans query_params ou session_state (retour depuis autre page)
            classification_ids = None
            if "_table_product_ids" in st.session_state:
                classification_ids = st.session_state["_table_product_ids"]
                print(f"DEBUG: Tableau vide mais IDs trouvés dans session_state: {classification_ids}")
            else:
                ids_param = st.query_params.get("table_product_ids", "")
                if ids_param:
                    classification_ids = [int(id_str) for id_str in ids_param.split(",") if id_str.strip().isdigit()]
                    if classification_ids:
                        # Stocker aussi dans session_state pour persister entre pages
                        st.session_state["_table_product_ids"] = classification_ids
                        print(f"DEBUG: Tableau vide mais IDs trouvés dans query_params: {classification_ids}")
            
            if classification_ids:
                # Recharger le tableau depuis les IDs (retour depuis autre page après refresh)
                print(f"DEBUG: Rechargement du tableau depuis les IDs (retour depuis autre page)")
                try:
                    from classifications_db import load_classifications_by_ids, get_current_user_id
                    user_id = get_current_user_id()
                    if user_id:
                        loaded_data = load_classifications_by_ids(classification_ids, user_id)
                        st.session_state["table_products"] = loaded_data
                        st.session_state["_table_cleared"] = False
                        print(f"DEBUG: {len(loaded_data)} produit(s) rechargé(s) depuis les IDs: {classification_ids}")
                    else:
                        # Pas d'utilisateur, charger depuis la base
                        loaded_data = load_table_data()
                        st.session_state["table_products"] = loaded_data
                        st.session_state["_table_cleared"] = False
                except Exception as e:
                    print(f"DEBUG: Erreur lors du rechargement depuis les IDs: {e}, chargement depuis la base")
                    loaded_data = load_table_data()
                    st.session_state["table_products"] = loaded_data
                    st.session_state["_table_cleared"] = False
                
                # Stocker les IDs dans session_state et query_params
                current_ids = [e.get('id') for e in st.session_state.get("table_products", []) if e.get('id')]
                if current_ids:
                    st.session_state["_table_product_ids"] = current_ids
                    st.query_params["table_product_ids"] = ",".join(map(str, current_ids))
                    print(f"DEBUG: IDs du tableau stockés dans session_state et query_params: {current_ids}")
            else:
                # Pas d'IDs disponibles - charger depuis la base
                print(f"DEBUG: Tableau vide et flag inactif - aucun ID disponible - chargement depuis la base")
                loaded_data = load_table_data()
                st.session_state["table_products"] = loaded_data
                st.session_state["_table_cleared"] = False
                
                # Stocker les IDs dans session_state (persiste entre pages) et query_params (persiste après refresh)
                current_ids = [e.get('id') for e in loaded_data if e.get('id')]
                if current_ids:
                    st.session_state["_table_product_ids"] = current_ids
                    st.query_params["table_product_ids"] = ",".join(map(str, current_ids))
                    print(f"DEBUG: IDs du tableau stockés dans session_state et query_params: {current_ids}")

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
            
            // Définir la fonction globalement pour qu'elle soit accessible partout
            window.toggleSidebar = function() {{
                // Méthode 1: Chercher le bouton natif de Streamlit avec plusieurs sélecteurs
                const selectors = [
                    'button[kind="header"]',
                    '[data-testid="baseButton-header"]',
                    'button[aria-label*="sidebar"]',
                    'button[aria-label*="menu"]',
                    '[data-testid="stSidebar"] + button',
                    'header button:first-of-type'
                ];
                
                let sidebarButton = null;
                for (const selector of selectors) {{
                    sidebarButton = document.querySelector(selector);
                    if (sidebarButton) {{
                        break;
                    }}
                }}
                
                if (sidebarButton) {{
                    sidebarButton.click();
                    return;
                }}
                
                // Méthode 2: Forcer l'affichage/masquage de la sidebar directement
                const sidebar = document.querySelector('[data-testid="stSidebar"]');
                if (sidebar) {{
                    // Vérifier l'état actuel de la sidebar
                    const computedStyle = window.getComputedStyle(sidebar);
                    const isVisible = computedStyle.display !== 'none' && 
                                     computedStyle.visibility !== 'hidden' &&
                                     computedStyle.transform !== 'translateX(-100%)' &&
                                     !sidebar.classList.contains('css-1d391kg');
                    
                    if (isVisible) {{
                        // Fermer la sidebar
                        sidebar.style.display = 'none';
                        sidebar.style.transform = 'translateX(-100%)';
                        sidebar.style.visibility = 'hidden';
                        sidebar.style.opacity = '0';
                    }} else {{
                        // Ouvrir la sidebar
                        sidebar.style.display = 'block';
                        sidebar.style.transform = 'translateX(0)';
                        sidebar.style.visibility = 'visible';
                        sidebar.style.opacity = '1';
                    }}
                    
                    // Déclencher un événement pour notifier Streamlit
                    const event = new Event('sidebar-toggle', {{ bubbles: true }});
                    sidebar.dispatchEvent(event);
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
        # Réafficher l'historique pour la nouvelle recherche
        st.session_state["show_history"] = True
        
        # Traiter la requête avec validation préventive
        result = process_user_input(
            user_message, 
            st.session_state["chunks"], 
            st.session_state["emb"], 
            st.session_state["index"], 
        )
        
        # Gérer le retour (peut être un tuple ou une string pour compatibilité)
        if isinstance(result, tuple):
            response, warning_message = result
            if warning_message:
                st.warning(warning_message)
                # Stocker le message d'avertissement pour l'afficher avec la réponse
                st.session_state["_warning_message"] = warning_message
        else:
            response = result
            warning_message = None

        parsed_payload, parse_error = parse_structured_response(response)
        if parsed_payload:
            formatted_answer = format_response_markdown(parsed_payload)
            # Générer un ID unique pour cette réponse
            response_id = f"response_{int(time.time() * 1000)}"
            
            # Stocker la requête et la réponse pour les feedbacks
            st.session_state[f"query_{response_id}"] = user_message
            st.session_state[f"response_text_{response_id}"] = response
            
            st.session_state["messages"].append(("RAG", formatted_answer, response_id))
            new_entries = build_table_entries(parsed_payload.get("classifications", []))
            if new_entries:
                # Initialiser selected_entries pour éviter UnboundLocalError
                selected_entries = []
                
                # Vérifier si l'utilisateur a refusé de stocker ce produit
                refused_key = f"_refused_{response_id}"
                is_refused = st.session_state.get(refused_key, False)
                
                # Vérifier si cette réponse a déjà été sauvegardée pour éviter les doublons
                save_key = f"_saved_{response_id}"
                saving_key = f"_saving_{response_id}"  # Clé pour indiquer qu'une sauvegarde est en cours
                
                # Vérifier si déjà sauvegardé OU en cours de sauvegarde
                # Vérifier aussi dans query_params pour persister entre reruns (important avec cache Redis)
                is_saving = (saving_key in st.session_state) or (st.query_params.get(f"saving_{response_id}") == "true")
                is_saved = (save_key in st.session_state) or (st.query_params.get(f"saved_{response_id}") == "true")
                
                # Si une seule classification, sauvegarder automatiquement
                if len(new_entries) == 1 and not is_saved and not is_saving and not is_refused:
                    # Sauvegarder automatiquement la seule classification
                    from classifications_db import save_classifications, get_current_user_id
                    user_id = get_current_user_id()
                    
                    if user_id:
                        # Marquer IMMÉDIATEMENT comme en cours de sauvegarde AVANT de commencer
                        st.session_state[saving_key] = True
                        st.query_params[f"saving_{response_id}"] = "true"
                        print(f"DEBUG: Sauvegarde automatique (1 seule classification) - response_id={response_id}, user_id={user_id}")
                        
                        with st.spinner("💾 Sauvegarde automatique en cours..."):
                            success, message, saved_ids = save_classifications(new_entries, user_id)
                        print(f"DEBUG: Fin sauvegarde automatique - response_id={response_id}, success={success}, message={message}, saved_ids={saved_ids}")
                        
                        if success:
                            # Marquer comme sauvegardé
                            st.session_state[save_key] = True
                            st.query_params[f"saved_{response_id}"] = "true"
                            # Retirer le flag de sauvegarde en cours
                            if saving_key in st.session_state:
                                del st.session_state[saving_key]
                            if f"saving_{response_id}" in st.query_params:
                                del st.query_params[f"saving_{response_id}"]
                            
                            # Mettre à jour le tableau avec la nouvelle classification et ajouter les IDs
                            table_was_cleared = st.session_state.get("_table_cleared", False) or st.query_params.get("table_cleared") == "true"
                            
                            if table_was_cleared:
                                # Si le tableau était vidé, juste ajouter les nouvelles classifications
                                # NE PAS réinitialiser le flag table_cleared - il doit rester actif
                                # pour que lors du refresh, on ne recharge pas toutes les données
                                current_table = st.session_state.get("table_products", [])
                                # Ajouter les IDs aux nouvelles entrées et les ajouter au tableau
                                # Permettre de classer le même produit plusieurs fois
                                for idx, entry in enumerate(new_entries):
                                    # Ajouter l'ID si disponible
                                    if idx < len(saved_ids) and saved_ids[idx]:
                                        entry['id'] = saved_ids[idx]
                                    current_table.append(entry)
                                st.session_state["table_products"] = current_table
                                
                                # Mettre à jour les IDs dans session_state (persiste entre pages) et query_params (persiste après refresh)
                                current_ids = [e.get('id') for e in current_table if e.get('id')]
                                if current_ids:
                                    st.session_state["_table_product_ids"] = current_ids
                                    st.query_params["table_product_ids"] = ",".join(map(str, current_ids))
                                    print(f"DEBUG: IDs du tableau stockés dans session_state et query_params: {current_ids}")
                                # Garder le flag table_cleared actif pour persister après refresh
                                st.session_state["_table_cleared"] = True
                                st.query_params["table_cleared"] = "true"
                                # S'assurer que le flag est aussi dans la DB
                                try:
                                    from database import get_db
                                    db = get_db()
                                    if db.test_connection():
                                        update_query = "UPDATE users SET table_cleared = 1 WHERE user_id = %s"
                                        db.execute_update(update_query, (user_id,))
                                        print(f"DEBUG: Flag table_cleared maintenu actif après ajout de produit")
                                except Exception as e:
                                    print(f"DEBUG: Erreur lors de la mise à jour du flag table_cleared: {e}")
                            else:
                                # Si le tableau n'était pas vidé, ajouter le nouveau produit
                                # Permettre de classer le même produit plusieurs fois
                                current_table = st.session_state.get("table_products", [])
                                
                                # Ajouter les IDs aux nouvelles entrées
                                for idx, entry in enumerate(new_entries):
                                    if idx < len(saved_ids) and saved_ids[idx]:
                                        entry['id'] = saved_ids[idx]
                                
                                # Toujours ajouter les nouvelles entrées, même si le produit existe déjà
                                # L'utilisateur peut vouloir classer le même produit plusieurs fois
                                st.session_state["table_products"] = current_table + new_entries
                                print(f"DEBUG: {len(new_entries)} produit(s) ajouté(s) au tableau")
                                
                                # Mettre à jour les IDs dans session_state (persiste entre pages) et query_params (persiste après refresh)
                                updated_table = st.session_state.get("table_products", [])
                                current_ids = [e.get('id') for e in updated_table if e.get('id')]
                                if current_ids:
                                    st.session_state["_table_product_ids"] = current_ids
                                    st.query_params["table_product_ids"] = ",".join(map(str, current_ids))
                                    print(f"DEBUG: IDs du tableau mis à jour dans session_state et query_params: {current_ids}")
                                # Ne PAS recharger tous les produits depuis la base si le tableau était vide
                                # Les nouveaux produits ont déjà été ajoutés ci-dessus
                            
                            st.success("✅ Classification sauvegardée automatiquement")
                            st.rerun()  # Recharger la page pour afficher le tableau mis à jour
                        else:
                            # Afficher l'erreur
                            st.error(f"❌ Erreur lors de la sauvegarde: {message}")
                            # Retirer le flag de sauvegarde en cours
                            if saving_key in st.session_state:
                                del st.session_state[saving_key]
                            if f"saving_{response_id}" in st.query_params:
                                del st.query_params[f"saving_{response_id}"]
                    else:
                        # Debug: pourquoi user_id est None
                        user = st.session_state.get("user")
                        print(f"DEBUG: user_id est None. user dans session_state: {user}")
                        if user:
                            print(f"DEBUG: user contient 'user_id': {'user_id' in user}")
                            print(f"DEBUG: user contient 'identifiant_user': {'identifiant_user' in user}")
                        st.warning("⚠️ Utilisateur non identifié. Les données sont enregistrées localement mais pas dans la base de données.")
                        st.write(f"🔍 Debug: session_state['user'] = {st.session_state.get('user')}")
                        st.write(f"🔍 Debug: query_params['user_id'] = {st.query_params.get('user_id')}")
                        
                        # Retirer le flag de sauvegarde en cours
                        if f"saving_{response_id}" in st.query_params:
                            del st.query_params[f"saving_{response_id}"]
                            
                            # Mettre à jour le tableau
                            table_was_cleared = st.session_state.get("_table_cleared", False) or st.query_params.get("table_cleared") == "true"
                            if table_was_cleared:
                                # Si le tableau était vidé, juste ajouter les nouvelles classifications
                                # Ne pas recharger les anciennes données - elles restent exclues
                                current_table = st.session_state.get("table_products", [])
                                # Ajouter les IDs aux nouvelles entrées
                                for idx, entry in enumerate(new_entries):
                                    if idx < len(saved_ids) and saved_ids[idx]:
                                        entry['id'] = saved_ids[idx]
                                st.session_state["table_products"] = current_table + new_entries
                                
                                # Mettre à jour les IDs dans session_state (persiste entre pages) et query_params (persiste après refresh)
                                updated_table = st.session_state.get("table_products", [])
                                current_ids = [e.get('id') for e in updated_table if e.get('id')]
                                if current_ids:
                                    st.session_state["_table_product_ids"] = current_ids
                                    st.query_params["table_product_ids"] = ",".join(map(str, current_ids))
                                    print(f"DEBUG: IDs du tableau mis à jour dans session_state et query_params: {current_ids}")
                                
                                # Garder le flag table_cleared pour que les anciens produits ne réapparaissent pas
                            else:
                                # Si le tableau n'était pas vidé, ajouter le nouveau produit au tableau existant
                                # Permettre de classer le même produit plusieurs fois
                                current_table = st.session_state.get("table_products", [])
                                # Toujours ajouter les nouvelles entrées, même si le produit existe déjà
                                st.session_state["table_products"] = current_table + new_entries
                                print(f"DEBUG: {len(new_entries)} produit(s) ajouté(s) au tableau")
                                
                                # Mettre à jour les IDs dans session_state (persiste entre pages) et query_params (persiste après refresh)
                                updated_table = st.session_state.get("table_products", [])
                                current_ids = [e.get('id') for e in updated_table if e.get('id')]
                                if current_ids:
                                    st.session_state["_table_product_ids"] = current_ids
                                    st.query_params["table_product_ids"] = ",".join(map(str, current_ids))
                                    print(f"DEBUG: IDs du tableau mis à jour dans session_state et query_params: {current_ids}")
                                
                                # Ne PAS recharger tous les produits depuis la base si le tableau était vide
                                # Les nouveaux produits ont déjà été ajoutés ci-dessus
                            
                            # Récupérer les IDs pour les feedbacks
                            try:
                                from database import get_db
                                db = get_db()
                                if db.test_connection():
                                    descriptions = st.session_state[f"_saved_descriptions_{response_id}"]
                                    if descriptions:
                                        try:
                                            from database import _get_db_type
                                            is_postgresql = (_get_db_type() == 'postgresql')
                                        except:
                                            is_postgresql = False
                                        
                                        if is_postgresql:
                                            query = """
                                            SELECT id FROM classifications 
                                            WHERE user_id = %s 
                                            AND description_produit = ANY(%s)
                                            AND date_classification >= NOW() - INTERVAL '1 minute'
                                            ORDER BY id DESC
                                            LIMIT %s
                                            """
                                            results = db.execute_query(query, (user_id, descriptions, len(descriptions)))
                                        else:
                                            placeholders = ','.join(['%s'] * len(descriptions))
                                            query = f"""
                                            SELECT id FROM classifications 
                                            WHERE user_id = %s 
                                            AND description_produit IN ({placeholders})
                                            AND date_classification >= DATE_SUB(NOW(), INTERVAL 1 MINUTE)
                                            ORDER BY id DESC
                                            LIMIT %s
                                            """
                                            results = db.execute_query(query, (user_id, *descriptions, len(descriptions)))
                                        if results:
                                            classification_ids = [row.get('id') for row in results if row.get('id')]
                                            if classification_ids:
                                                st.session_state[f"classification_ids_{response_id}"] = classification_ids
                            except Exception as e:
                                print(f"Erreur lors de la récupération des IDs: {e}")
                        else:
                            if saving_key in st.session_state:
                                del st.session_state[saving_key]
                            if f"saving_{response_id}" in st.query_params:
                                del st.query_params[f"saving_{response_id}"]
                            st.error(f"⚠️ Erreur lors de la sauvegarde: {message}")
                else:
                    # Utilisateur non identifié - ne pas sauvegarder
                    pass
                    st.warning("⚠️ Utilisateur non identifié. Les données sont enregistrées localement mais pas dans la base de données.")
                    st.write(f"🔍 Debug: session_state['user'] = {st.session_state.get('user')}")
                    st.write(f"🔍 Debug: query_params['user_id'] = {st.query_params.get('user_id')}")
        else:
            fallback_text = response or f"⚠️ {parse_error}"
            response_id = f"response_{int(time.time() * 1000)}"
            
            # Stocker la requête et la réponse pour les feedbacks même en cas d'erreur
            st.session_state[f"query_{response_id}"] = user_message
            st.session_state[f"response_text_{response_id}"] = fallback_text
            
            st.session_state["messages"].append(("RAG", fallback_text, response_id))

        spinner_placeholder.empty()
        
        # Afficher les messages d'erreur s'ils existent
        if "_save_error" in st.session_state:
            st.error(f"⚠️ Erreur lors de la sauvegarde: {st.session_state['_save_error']}")
            del st.session_state["_save_error"]
        # Ne plus afficher les messages de succès (supprimé à la demande de l'utilisateur)
        if "_save_success" in st.session_state:
            del st.session_state["_save_success"]
        
        # Ne faire rerun que si une sauvegarde ne vient pas de se terminer
        # Cela évite les duplications avec le cache Redis
        if not st.session_state.get("_just_saved", False):
            st.rerun()
        else:
            # Retirer le flag après avoir évité le rerun
            del st.session_state["_just_saved"]
    
    # Initialiser le dictionnaire des notes si nécessaire
    if "response_ratings" not in st.session_state:
        st.session_state["response_ratings"] = {}
    
    # Initialiser show_history si nécessaire (par défaut True pour afficher)
    if "show_history" not in st.session_state:
        st.session_state["show_history"] = True
    
    # Zone de chat
    if st.session_state["messages"]:
        # Vérifier si l'historique doit être affiché
        show_history = st.session_state.get("show_history", True)
        if show_history:
            # Afficher les messages style cartoon
            for i in range(0, len(st.session_state["messages"]), 2):
                if i < len(st.session_state["messages"]):
                    # Gérer les anciens messages sans ID (rétrocompatibilité)
                    if len(st.session_state["messages"][i]) == 2:
                        user, user_message = st.session_state["messages"][i]
                    else:
                        user, user_message, _ = st.session_state["messages"][i]
                    st.markdown(f"""
                        <div class="user-message">
                            <strong style="font-size: 1.1rem; font-weight: 700; display: block; margin-bottom: 0.5rem;">👤 Vous</strong>
                            <div style="line-height: 1.6; font-size: 1rem;">{user_message}</div>
                        </div>
                    """, unsafe_allow_html=True)
                
                if i + 1 < len(st.session_state["messages"]):
                    # Gérer les anciens messages sans ID (rétrocompatibilité)
                    if len(st.session_state["messages"][i + 1]) == 2:
                        rag, rag_message = st.session_state["messages"][i + 1]
                        response_id = f"response_legacy_{i}"
                    else:
                        rag, rag_message, response_id = st.session_state["messages"][i + 1]
                    
                    # Afficher le message de Mosam
                    st.markdown(f"""
                        <div class="rag-message">
                            <strong style="font-size: 1.1rem; font-weight: 700; display: block; margin-bottom: 0.5rem;">🤖 Mosam</strong>
                            <div style="line-height: 1.6; font-size: 1rem;">{rag_message}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Boutons de notation et de refus de stockage
                    col1, col2, col3, col4 = st.columns([1, 1, 2.5, 7.5])
                    with col1:
                        current_rating = st.session_state["response_ratings"].get(response_id, None)
                        if current_rating == "up":
                            button_style_up = "background: #4CAF50; color: white;"
                        else:
                            button_style_up = "background: white; color: #4CAF50; border: 2px solid #4CAF50;"
                        
                        if st.button("👍", key=f"up_{response_id}", use_container_width=True):
                            classification_ids = st.session_state.get(f"classification_ids_{response_id}", [])
                            
                            if current_rating == "up":
                                # Retirer la note si déjà noté positivement
                                del st.session_state["response_ratings"][response_id]
                                # Supprimer le feedback de la base de données
                                try:
                                    from feedback_db import remove_feedback
                                    if classification_ids:
                                        remove_feedback(classification_ids)
                                except Exception as e:
                                    print(f"Erreur lors de la suppression du feedback: {e}")
                            else:
                                # Si l'utilisateur avait cliqué sur 👎, retirer d'abord le feedback négatif
                                if current_rating == "down":
                                    try:
                                        from feedback_db import remove_feedback
                                        if classification_ids:
                                            remove_feedback(classification_ids)
                                    except Exception as e:
                                        print(f"Erreur lors de la suppression du feedback précédent: {e}")
                                
                                # Ajouter le feedback positif
                                st.session_state["response_ratings"][response_id] = "up"
                                try:
                                    from feedback_db import save_feedback
                                    user_query = st.session_state.get(f"query_{response_id}", "")
                                    if user_query and classification_ids:
                                        success, message = save_feedback(user_query, classification_ids, "up")
                                        if success:
                                            st.success("✅ Note positive enregistrée")
                                except Exception as e:
                                    print(f"Erreur lors de la sauvegarde du feedback: {e}")
                            st.rerun()
                    
                    with col2:
                        if current_rating == "down":
                            button_style_down = "background: #f44336; color: white;"
                        else:
                            button_style_down = "background: white; color: #f44336; border: 2px solid #f44336;"
                        
                        if st.button("👎", key=f"down_{response_id}", use_container_width=True):
                            classification_ids = st.session_state.get(f"classification_ids_{response_id}", [])
                            
                            if current_rating == "down":
                                # Retirer la note si déjà noté négativement
                                del st.session_state["response_ratings"][response_id]
                                # Supprimer le feedback de la base de données
                                try:
                                    from feedback_db import remove_feedback
                                    if classification_ids:
                                        remove_feedback(classification_ids)
                                except Exception as e:
                                    print(f"Erreur lors de la suppression du feedback: {e}")
                            else:
                                # Si l'utilisateur avait cliqué sur 👍, retirer d'abord le feedback positif
                                if current_rating == "up":
                                    try:
                                        from feedback_db import remove_feedback
                                        if classification_ids:
                                            remove_feedback(classification_ids)
                                    except Exception as e:
                                        print(f"Erreur lors de la suppression du feedback précédent: {e}")
                                
                                # Ajouter le feedback négatif
                                st.session_state["response_ratings"][response_id] = "down"
                                try:
                                    from feedback_db import save_feedback
                                    user_query = st.session_state.get(f"query_{response_id}", "")
                                    if user_query and classification_ids:
                                        success, message = save_feedback(user_query, classification_ids, "down")
                                        if success:
                                            st.warning("⚠️ Note négative enregistrée. Cette information aidera à améliorer le système.")
                                except Exception as e:
                                    print(f"Erreur lors de la sauvegarde du feedback: {e}")
                            st.rerun()
                    
                    with col3:
                        # Vérifier si le produit a été refusé
                        refused_key = f"_refused_{response_id}"
                        is_refused = st.session_state.get(refused_key, False)
                        
                        if is_refused:
                            button_style_refuse = "background: #ff9800; color: white;"
                        else:
                            button_style_refuse = "background: white; color: #ff9800; border: 2px solid #ff9800;"
                        
                        if st.button("🚫 Ne pas stocker", key=f"refuse_{response_id}", use_container_width=True):
                            classification_ids = st.session_state.get(f"classification_ids_{response_id}", [])
                            if classification_ids:
                                try:
                                    from classifications_db import delete_classifications_by_ids, get_current_user_id
                                    user_id = get_current_user_id()
                                    success, message = delete_classifications_by_ids(classification_ids, user_id)
                                    if success:
                                        # Marquer comme refusé
                                        st.session_state[refused_key] = True
                                        # Supprimer les IDs des classifications supprimées
                                        del st.session_state[f"classification_ids_{response_id}"]
                                        # Ne pas recharger depuis la base si le tableau a été vidé
                                        # L'utilisateur peut recharger manuellement si nécessaire
                                        table_cleared = st.session_state.get("_table_cleared", False) or st.query_params.get("table_cleared") == "true"
                                        if not table_cleared:
                                            from classifications_db import load_table_data
                                            loaded_data = load_table_data()
                                            st.session_state["table_products"] = loaded_data
                                            
                                            # Mettre à jour les IDs dans session_state (persiste entre pages) et query_params (persiste après refresh)
                                            current_ids = [e.get('id') for e in loaded_data if e.get('id')]
                                            if current_ids:
                                                st.session_state["_table_product_ids"] = current_ids
                                                st.query_params["table_product_ids"] = ",".join(map(str, current_ids))
                                                print(f"DEBUG: IDs du tableau mis à jour dans session_state et query_params: {current_ids}")
                                        else:
                                            # Si le tableau était vidé, mettre à jour les IDs en supprimant celui qui a été retiré
                                            current_table = st.session_state.get("table_products", [])
                                            current_ids = [e.get('id') for e in current_table if e.get('id')]
                                            if current_ids:
                                                st.session_state["_table_product_ids"] = current_ids
                                                st.query_params["table_product_ids"] = ",".join(map(str, current_ids))
                                                print(f"DEBUG: IDs du tableau mis à jour après suppression: {current_ids}")
                                        st.warning("⚠️ Produit retiré du stockage")
                                    else:
                                        st.error(f"❌ Erreur: {message}")
                                except Exception as e:
                                    st.error(f"❌ Erreur lors de la suppression: {e}")
                                    print(f"Erreur lors de la suppression des classifications: {e}")
                            else:
                                # Si pas encore sauvegardé, marquer comme refusé pour éviter la sauvegarde
                                st.session_state[refused_key] = True
                                st.warning("⚠️ Ce produit ne sera pas stocké")
                            st.rerun()
            
            # Bouton pour fermer l'historique avec style moderne
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("Fermer l'historique", use_container_width=True):
                    # Cacher l'historique
                    st.session_state["show_history"] = False
                    st.rerun()
    
    # Afficher le nombre de produits classés avec style moderne
    # Utiliser les données du tableau local (session_state) pour respecter le vidage intentionnel
    table_data = st.session_state.get("table_products", [])
    product_count = len(table_data)
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
    
    # Restaurer la session depuis le cookie/query params si nécessaire
    from auth_db import restore_session_from_cookie
    restore_session_from_cookie()
    
    # Vérifier l'authentification
    if not is_authenticated():
        st.switch_page("pages/Login.py")
        return
    
    # CRITIQUE: Récupérer table_cleared_db APRÈS l'authentification pour s'assurer que get_current_user_id() fonctionne
    # Cela garantit que le flag est correctement récupéré lors de la reconnexion
    global table_cleared_db
    try:
        from classifications_db import get_current_user_id
        from database import get_db
        user_id = get_current_user_id()
        if user_id:
            db = get_db()
            if db.test_connection():
                try:
                    query = "SELECT table_cleared FROM users WHERE user_id = %s"
                    result = db.execute_query(query, (user_id,))
                    if result and len(result) > 0:
                        table_cleared_db = bool(result[0].get('table_cleared', False))
                        print(f"DEBUG main: table_cleared_db récupéré depuis la DB: {table_cleared_db}")
                except Exception as e:
                    # La colonne n'existe peut-être pas encore, ignorer
                    print(f"Note: table_cleared column may not exist: {e}")
    except Exception as e:
        print(f"Erreur lors de la récupération de la préférence table_cleared dans main(): {e}")
    
    # CRITIQUE: Si table_cleared_db est True, vider le tableau même s'il a déjà été initialisé au niveau global
    # Cela garantit que lors de la reconnexion, le tableau reste vide si l'utilisateur l'avait vidé avant
    if table_cleared_db:
        # Le tableau a été vidé avant la déconnexion, s'assurer qu'il reste vide
        st.session_state["table_products"] = []
        st.session_state["_table_cleared"] = True
        st.query_params["table_cleared"] = "true"
        # Supprimer les IDs du tableau car il a été vidé
        if "_table_product_ids" in st.session_state:
            del st.session_state["_table_product_ids"]
        if "table_product_ids" in st.query_params:
            del st.query_params["table_product_ids"]
        print(f"DEBUG main: Tableau vidé car table_cleared_db=True (reconnexion après déconnexion)")
    
    # Afficher les informations de l'utilisateur dans la sidebar
    current_user = get_current_user()
    if current_user:
        # S'assurer que l'identifiant est dans les query params pour la persistance
        if not st.query_params.get('user_id'):
            st.query_params['user_id'] = current_user.get('identifiant_user', '')
        
        # Conteneur avec fond blanc pour les informations utilisateur
        st.sidebar.markdown(f"""
            <div class="user-info-container">
                <h3 style="color: {DOUANE_VERT}; margin-top: 0; margin-bottom: 0.5rem;">👤 {current_user.get('nom_user', 'Utilisateur')}</h3>
                <p style="color: #666; margin: 0.25rem 0; font-size: 0.9rem;">*{current_user.get('email', '')}*</p>
                {"<p style='color: " + DOUANE_OR + "; margin: 0.5rem 0 0 0; font-weight: 600;'>👑 Administrateur</p>" if current_user.get('is_admin') else ""}
            </div>
        """, unsafe_allow_html=True)
        
        if st.sidebar.button("👤 Mon Profil", use_container_width=True):
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
                    print(f"DEBUG app.py navigation: IDs récupérés depuis session_state: {ids_list}")
            elif "table_product_ids" in st.query_params:
                preserve_params["table_product_ids"] = st.query_params["table_product_ids"]
            
            if "user_id" in st.query_params:
                preserve_params["user_id"] = st.query_params["user_id"]
            
            # Appliquer les paramètres préservés dans l'URL (CRITIQUE pour que ça reste après refresh)
            for key, value in preserve_params.items():
                if value is not None:  # Ne pas mettre None dans query_params
                    st.query_params[key] = value
                    print(f"DEBUG app.py navigation: Paramètre préservé dans URL: {key}={value}")
            
            st.switch_page("pages/Profil.py")
        if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
            logout()
    
    display_main_content()

if __name__ == "__main__":
    main()
