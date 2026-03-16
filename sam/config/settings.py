"""
Configuration file for the Mosam CEDEAO tariff-classification assistant.
"""
import os
from dotenv import load_dotenv

# Charge les variables d'environnement depuis le fichier .env à la racine du projet.
load_dotenv()


class Config:
    """Configuration centralisée de l'application."""

    # LLM / OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    MOSAM_MODEL = os.getenv("MOSAM_MODEL", "gpt-4.1-mini")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Base de données (Supabase / Postgres)
    SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

    # Cache Redis (Upstash)
    UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
    UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

