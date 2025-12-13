"""
Configuration file for the Mosam CEDEAO tariff-classification assistant.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
