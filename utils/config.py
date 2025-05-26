"""
Centralized configuration management with strict validation
"""

import os
from typing import Optional
from pydantic import BaseSettings, validator
from functools import lru_cache


class Config(BaseSettings):
    """Application configuration with validation"""
    
    # Database
    postgres_url: str
    postgres_url_non_pooling: Optional[str] = None
    
    # Supabase
    supabase_url: str
    supabase_jwt_secret: str
    supabase_service_role_key: str
    supabase_anon_key: str
    
    # OpenAI
    openai_api_key: str
    
    # Instagram
    instagram_app_id: str
    instagram_app_secret: str
    
    # Twitter
    twitter_consumer_key: str
    twitter_consumer_secret: str
    
    # YouTube
    youtube_client_id: str
    youtube_client_secret: str
    
    # LinkedIn
    linkedin_client_id: str
    linkedin_client_secret: str
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # Application
    environment: str = "development"
    log_level: str = "INFO"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @validator('postgres_url')
    def validate_postgres_url(cls, v):
        if not v:
            raise ValueError("POSTGRES_URL is required")
        return v
    
    @validator('supabase_url')
    def validate_supabase_url(cls, v):
        if not v or not v.startswith('https://'):
            raise ValueError("SUPABASE_URL must be a valid HTTPS URL")
        return v
    
    @validator('openai_api_key')
    def validate_openai_key(cls, v):
        if not v or not v.startswith('sk-'):
            raise ValueError("OPENAI_API_KEY must be a valid OpenAI API key")
        return v


@lru_cache()
def get_config() -> Config:
    """Get cached configuration instance"""
    try:
        return Config()
    except Exception as e:
        raise RuntimeError(f"Configuration validation failed: {str(e)}")


def validate_config_on_startup():
    """Validate configuration at application startup"""
    try:
        config = get_config()
        
        # Additional runtime validations
        required_secrets = [
            config.postgres_url,
            config.supabase_url,
            config.supabase_jwt_secret,
            config.openai_api_key,
            config.instagram_app_secret,
            config.twitter_consumer_secret,
            config.youtube_client_secret,
            config.linkedin_client_secret,
        ]
        
        missing_secrets = [name for name, value in zip([
            "POSTGRES_URL", "SUPABASE_URL", "SUPABASE_JWT_SECRET", 
            "OPENAI_API_KEY", "INSTAGRAM_APP_SECRET", "TWITTER_CONSUMER_SECRET",
            "YOUTUBE_CLIENT_SECRET", "LINKEDIN_CLIENT_SECRET"
        ], required_secrets) if not value]
        
        if missing_secrets:
            raise ValueError(f"Missing required configuration: {', '.join(missing_secrets)}")
        
        return config
        
    except Exception as e:
        raise RuntimeError(f"Configuration validation failed: {str(e)}")
