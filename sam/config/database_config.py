"""
Configuration de la base de données
Peut être surchargée par des variables d'environnement ou Streamlit secrets
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger le .env depuis la racine du projet
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Fallback to default .env location

# Configuration par défaut
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'douane_simple')
}

