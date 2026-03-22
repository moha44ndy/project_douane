"""
Configuration file for the Mosam CEDEAO tariff-classification assistant.
"""
import os
from dotenv import load_dotenv

# Racine du dépôt (parent de `sam/`), pour charger `.env` même si le CWD est `sam/` ou ailleurs.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ROOT_ENV = os.path.join(_REPO_ROOT, ".env")

load_dotenv(_ROOT_ENV)
# Fichier `.env` du répertoire courant peut surcharger (optionnel).
load_dotenv()

# Dans ce projet, certaines variables (dont `SUPABASE_JWT_SECRET`) peuvent être
# définies dans `frontend/.env.local`. Pour que le backend puisse aussi faire
# sa vérification JWT en prod, on les charge aussi si elles manquent.
if not os.getenv("SUPABASE_JWT_SECRET"):
    frontend_env_local = os.path.join(_REPO_ROOT, "frontend", ".env.local")
    load_dotenv(frontend_env_local, override=False)


class Config:
    """Configuration centralisée de l'application."""

    # LLM / OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    MOSAM_MODEL = os.getenv("MOSAM_MODEL", "gpt-4.1-mini")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Base de données (Supabase / Postgres)
    # Priorité au pooler (Session / Transaction) : souvent compatible IPv4 ; la connexion
    # « directe » db.*.supabase.co:5432 est souvent IPv6-only sur plan gratuit.
    SUPABASE_DB_URL = (
        os.getenv("SUPABASE_DB_POOLER_URL", "").strip()
        or os.getenv("SUPABASE_DB_URL", "").strip()
        or None
    )

    # Supabase Auth (API d'admin pour créer des comptes)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

    # Cache Redis (Upstash)
    UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
    UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

