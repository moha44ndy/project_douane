"""
Configuration file for the Mosam CEDEAO tariff-classification assistant.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file at project root
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Fallback to default .env location

class Config:
    """Configuration class for application settings."""
    # LLM API configuration (customs analysis)
    AUTH_URL = os.getenv('AUTH_URL')
    API_URL = os.getenv('API_URL')
    USER = os.getenv('USER')
    PASSWORD = os.getenv('PASSWORD')
    MODEL_DIR = os.getenv('MODEL_DIR')
    MODEL_ID = os.getenv('MODEL_ID')
    ARGOS_MODEL = os.getenv('ARGOS_MODEL')
