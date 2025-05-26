"""
Centralized configuration management with strict validation
"""

import os
from typing import Optional
from pydantic import BaseSettings, validator, Field
from functools import lru_cache


class Config(BaseSettings):
    """Application configuration with validation"""
    
    # Database
    postgres_url: str = Field(..., env="POSTGRES_URL")
    postgres_url_non_pooling: Optional[str] = Field(None, env="POSTGRES_URL_NON_POOLING")
    
    # Supabase
    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_jwt_secret: str = Field(..., env="SUPABASE_JWT_SECRET")
    supabase_service_role_key: str = Field(..., env="SUPABASE_SERVICE_ROLE_KEY")
    supabase_anon_key: str = Field(..., env="SUPABASE_ANON_KEY")
    
    # OpenAI
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    
    # Instagram
    instagram_app_id: str = Field(..., env="INSTAGRAM_APP_ID")
    instagram_app_secret: str = Field(..., env="INSTAGRAM_APP_SECRET")
    
    # Twitter
    twitter_consumer_key: str = Field(..., env="TWITTER_CONSUMER_KEY")
    twitter_consumer_secret: str = Field(..., env="TWITTER_CONSUMER_SECRET")
    
    # YouTube
    youtube_client_id: str = Field(..., env="YOUTUBE_CLIENT_ID")
    youtube_client_secret: str = Field(..., env="YOUTUBE_CLIENT_SECRET")
    
    # LinkedIn
    linkedin_client_id: str = Field(..., env="LINKEDIN_CLIENT_ID")
    linkedin_client_secret: str = Field(..., env="LINKEDIN_CLIENT_SECRET")
    
    # Redis
    redis_url: str = Field("redis://localhost:6379", env="REDIS_URL")
    
    # Application
    environment: str = Field("development", env="ENVIRONMENT")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    port: int = Field(8000, env="PORT")
    
    # Security
    webhook_secret_key: str = Field(..., env="WEBHOOK_SECRET_KEY")
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        validate_assignment = True
    
    @validator('postgres_url')
    def validate_postgres_url(cls, v):
        if not v:
            raise ValueError("POSTGRES_URL is required")
        if not v.startswith(('postgresql://', 'postgres://')):
            raise ValueError("POSTGRES_URL must be a valid PostgreSQL connection string")
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
    
    @validator('redis_url')
    def validate_redis_url(cls, v):
        if not v.startswith('redis://'):
            raise ValueError("REDIS_URL must be a valid Redis connection string")
        return v
    
    @validator('environment')
    def validate_environment(cls, v):
        if v not in ['development', 'staging', 'production']:
            raise ValueError("ENVIRONMENT must be one of: development, staging, production")
        return v


@lru_cache()
def get_config() -> Config:
    """Get cached configuration instance"""
    try:
        return Config()
    except Exception as e:
        raise RuntimeError(f"Configuration validation failed: {str(e)}")


def validate_config_on_startup():
    """Validate configuration at application startup with detailed checks"""
    try:
        config = get_config()
        
        # Test critical connections
        critical_configs = {
            "Database": config.postgres_url,
            "Supabase": config.supabase_url,
            "OpenAI": config.openai_api_key,
            "Redis": config.redis_url,
        }
        
        missing_configs = [name for name, value in critical_configs.items() if not value]
        
        if missing_configs:
            raise ValueError(f"Missing critical configuration: {', '.join(missing_configs)}")
        
        # Validate platform secrets
        platform_secrets = {
            "Instagram": [config.instagram_app_id, config.instagram_app_secret],
            "Twitter": [config.twitter_consumer_key, config.twitter_consumer_secret],
            "YouTube": [config.youtube_client_id, config.youtube_client_secret],
            "LinkedIn": [config.linkedin_client_id, config.linkedin_client_secret],
        }
        
        missing_platform_secrets = []
        for platform, secrets in platform_secrets.items():
            if not all(secrets):
                missing_platform_secrets.append(platform)
        
        if missing_platform_secrets:
            raise ValueError(f"Missing platform secrets for: {', '.join(missing_platform_secrets)}")
        
        return config
        
    except Exception as e:
        raise RuntimeError(f"Configuration validation failed: {str(e)}")
