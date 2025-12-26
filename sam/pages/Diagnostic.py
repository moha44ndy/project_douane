"""
Page de diagnostic pour la connexion à la base de données
Système de Classification Douanière CEDEAO
"""
import streamlit as st
import sys
import os
from pathlib import Path
import socket
import traceback

st.set_page_config(
    page_title="Diagnostic Base de Données",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Diagnostic Connexion Base de Données")

st.markdown("""
Cette page permet de diagnostiquer les problèmes de connexion à la base de données en production.
""")

# Exécuter le diagnostic
if st.button("🔍 Lancer le Diagnostic", type="primary"):
    with st.spinner("Exécution du diagnostic..."):
        # Capturer la sortie
        import io
        from contextlib import redirect_stdout
        
        output = io.StringIO()
        
        try:
            with redirect_stdout(output):
                # Importer et exécuter le script de diagnostic
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from tools.diagnose_production_db import *
            
            result = output.getvalue()
            st.code(result, language="text")
            
        except Exception as e:
            st.error(f"Erreur lors de l'exécution du diagnostic: {e}")
            st.code(traceback.format_exc(), language="python")

# Section manuelle de test
st.markdown("---")
st.subheader("🧪 Test Manuel de Connexion")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Configuration Détectée")
    try:
        if hasattr(st, 'secrets') and 'database' in st.secrets:
            db_secrets = st.secrets['database']
            
            if 'connection_string' in db_secrets:
                conn_str = db_secrets['connection_string']
                # Masquer le mot de passe
                if '@' in conn_str:
                    parts = conn_str.split('@')
                    if ':' in parts[0]:
                        user_pass = parts[0].split(':')
                        if len(user_pass) >= 2:
                            masked = f"{user_pass[0]}:***@{parts[1]}"
                        else:
                            masked = conn_str
                    else:
                        masked = conn_str
                else:
                    masked = conn_str
                st.code(f"connection_string = {masked}", language="toml")
            else:
                st.code(f"""
host = {db_secrets.get('host', 'NON DÉFINI')}
port = {db_secrets.get('port', 'NON DÉFINI')}
user = {db_secrets.get('user', 'NON DÉFINI')}
password = {'***' if db_secrets.get('password') else 'NON DÉFINI'}
database = {db_secrets.get('database', 'NON DÉFINI')}
""", language="toml")
        else:
            st.warning("⚠️ Aucune configuration trouvée dans les secrets")
    except Exception as e:
        st.error(f"Erreur: {e}")

with col2:
    st.markdown("### Test de Connexion")
    if st.button("🔌 Tester la Connexion"):
        try:
            from database import get_db
            db = get_db()
            
            with st.spinner("Connexion en cours..."):
                if db.test_connection():
                    st.success("✅ Connexion réussie!")
                    
                    # Tester une requête
                    try:
                        result = db.execute_query("SELECT version();")
                        if result:
                            version = result[0].get('version', 'N/A')
                            st.info(f"Version: {version[:100]}...")
                    except Exception as e:
                        st.warning(f"Connexion OK mais erreur requête: {e}")
                else:
                    st.error("❌ Échec de la connexion")
        except Exception as e:
            st.error(f"❌ Erreur: {e}")
            st.code(traceback.format_exc(), language="python")

# Section résolution DNS
st.markdown("---")
st.subheader("🌐 Résolution DNS")

if st.button("🔍 Résoudre le Hostname"):
    try:
        if hasattr(st, 'secrets') and 'database' in st.secrets:
            db_secrets = st.secrets['database']
            hostname = None
            
            if 'connection_string' in db_secrets:
                import urllib.parse
                parsed = urllib.parse.urlparse(db_secrets['connection_string'])
                hostname = parsed.hostname
            elif 'host' in db_secrets:
                hostname = db_secrets['host']
            
            if hostname:
                st.info(f"Hostname: `{hostname}`")
                
                # IPv4
                try:
                    addrinfo_ipv4 = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
                    if addrinfo_ipv4:
                        ipv4 = addrinfo_ipv4[0][4][0]
                        st.success(f"✅ IPv4: `{ipv4}`")
                    else:
                        st.warning("⚠️ Aucune adresse IPv4 trouvée")
                except Exception as e:
                    st.error(f"❌ Erreur résolution IPv4: {e}")
                
                # IPv6
                try:
                    addrinfo_ipv6 = socket.getaddrinfo(hostname, None, socket.AF_INET6, socket.SOCK_STREAM)
                    if addrinfo_ipv6:
                        ipv6 = addrinfo_ipv6[0][4][0]
                        st.warning(f"⚠️ IPv6 détecté: `{ipv6}`")
                        st.warning("⚠️ L'utilisation d'IPv6 peut causer des problèmes de connexion!")
                    else:
                        st.success("✅ Aucune adresse IPv6 trouvée")
                except Exception as e:
                    st.info(f"ℹ️ Pas d'IPv6: {e}")
            else:
                st.warning("⚠️ Hostname non trouvé")
        else:
            st.warning("⚠️ Configuration non trouvée")
    except Exception as e:
        st.error(f"Erreur: {e}")
        st.code(traceback.format_exc(), language="python")

# Instructions
st.markdown("---")
st.subheader("📋 Instructions")

st.markdown("""
### Pour résoudre les problèmes de connexion :

1. **Vérifiez les secrets dans Streamlit Cloud** :
   - Allez dans Settings → Secrets
   - Vérifiez que la section `[database]` est correctement configurée

2. **Utilisez le port de pooling (6543)** :
   ```toml
   [database]
   host = "db.yrdhzpckptziyiefshga.supabase.co"
   port = 6543
   user = "postgres"
   password = "Douane2025#"
   database = "postgres"
   ```

3. **Vérifiez que Supabase est actif** :
   - Allez dans votre projet Supabase
   - Vérifiez qu'il n'est pas en pause

4. **Vérifiez les logs** :
   - Regardez les logs dans Streamlit Cloud → Manage app → Logs
   - Cherchez les erreurs spécifiques
""")

