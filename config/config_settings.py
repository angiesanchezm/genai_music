"""
Configuración centralizada de la aplicación
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """Configuración de la aplicación usando variables de entorno"""
    
    # OpenAI GPT-5
    openai_api_key: str
    openai_model: str = "gpt-5"
    max_tokens_response: int = 500
    temperature: float = 0.7
    
    # Pinecone
    pinecone_api_key: str
    pinecone_environment: str
    pinecone_index_name: str
    
    # WhatsApp
    whatsapp_api_token: str
    whatsapp_phone_number_id: str
    whatsapp_verify_token: str
    whatsapp_api_version: str = "v18.0"
    
    # Application
    environment: str = "development"
    log_level: str = "INFO"
    
    # Security
    rate_limit_messages_per_minute: int = 10
    enable_security_validation: bool = True
    
    # Priority Scoring
    priority_threshold_high: float = 7.0
    priority_threshold_critical: float = 9.0
    
    # Database
    database_path: str = "./data/database/conversations.db"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Instancia global de configuración
settings = Settings()
