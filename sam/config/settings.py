"""
Configuration file for the Mosam CEDEAO tariff-classification assistant.
"""
import os
from dotenv import load_dotenv

# Charge les variables d'environnement depuis le fichier .env à la racine du projet.
load_dotenv()

# Dans ce projet, certaines variables (dont `SUPABASE_JWT_SECRET`) peuvent être
# définies dans `frontend/.env.local`. Pour que le backend puisse aussi faire
# sa vérification JWT en prod, on les charge aussi si elles manquent.
if not os.getenv("SUPABASE_JWT_SECRET"):
    frontend_env_local = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", ".env.local"
    )
    load_dotenv(frontend_env_local, override=False)


class Config:
    """Configuration centralisée de l'application."""

    # LLM / OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    MOSAM_MODEL = os.getenv("MOSAM_MODEL", "gpt-4.1-mini")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Base de données (Supabase / Postgres)
    SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

    # Supabase Auth (API d'admin pour créer des comptes)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

    # Cache Redis (Upstash)
    UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
    UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

