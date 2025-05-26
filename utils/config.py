"""
Centralized configuration management with strict validation
"""

import os
from typing import Optional
from pydantic import validator, Field
from pydantic_settings import BaseSettings
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


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
    """Validate configuration at application startup with fail-fast approach"""
    try:
        config = get_config()
        
        # Critical secrets that must be present
        critical_secrets = {
            "POSTGRES_URL": config.postgres_url,
            "SUPABASE_URL": config.supabase_url,
            "SUPABASE_JWT_SECRET": config.supabase_jwt_secret,
            "SUPABASE_SERVICE_ROLE_KEY": config.supabase_service_role_key,
            "OPENAI_API_KEY": config.openai_api_key,
            "WEBHOOK_SECRET_KEY": config.webhook_secret_key,
            "JWT_SECRET_KEY": config.jwt_secret_key,
        }
        
        # Check for missing critical secrets
        missing_critical = [name for name, value in critical_secrets.items() if not value or len(value.strip()) == 0]
        if missing_critical:
            raise RuntimeError(f"CRITICAL: Missing required secrets: {', '.join(missing_critical)}. Application cannot start.")
        
        # Platform secrets validation
        platform_secrets = {
            "INSTAGRAM_APP_SECRET": config.instagram_app_secret,
            "TWITTER_CONSUMER_SECRET": config.twitter_consumer_secret,
            "YOUTUBE_CLIENT_SECRET": config.youtube_client_secret,
            "LINKEDIN_CLIENT_SECRET": config.linkedin_client_secret,
        }
        
        missing_platform = [name for name, value in platform_secrets.items() if not value or len(value.strip()) == 0]
        if missing_platform:
            raise RuntimeError(f"CRITICAL: Missing platform secrets: {', '.join(missing_platform)}. Webhook verification will fail.")
        
        # Validate secret formats
        if not config.openai_api_key.startswith('sk-'):
            raise RuntimeError("CRITICAL: OPENAI_API_KEY must start with 'sk-'")
        
        if not config.supabase_url.startswith('https://'):
            raise RuntimeError("CRITICAL: SUPABASE_URL must be a valid HTTPS URL")
        
        if len(config.webhook_secret_key) < 32:
            raise RuntimeError("CRITICAL: WEBHOOK_SECRET_KEY must be at least 32 characters")
        
        if len(config.jwt_secret_key) < 32:
            raise RuntimeError("CRITICAL: JWT_SECRET_KEY must be at least 32 characters")
        
        # Test database connection format
        if not any(config.postgres_url.startswith(prefix) for prefix in ['postgresql://', 'postgres://']):
            raise RuntimeError("CRITICAL: POSTGRES_URL must be a valid PostgreSQL connection string")
        
        logger.info("All configuration validation passed")
        return config
        
    except Exception as e:
        logger.error(f"CONFIGURATION VALIDATION FAILED: {str(e)}")
        raise SystemExit(f"Application startup aborted: {str(e)}")
