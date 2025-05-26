"""
Fail-fast configuration and secrets validation
"""

import os
import sys
from typing import List, Dict, Any
from utils.config import get_config
from utils.logging import get_logger

logger = get_logger(__name__)


class ConfigBootstrap:
    """Fail-fast configuration validator"""
    
    CRITICAL_SECRETS = [
        "POSTGRES_URL",
        "SUPABASE_URL", 
        "SUPABASE_JWT_SECRET",
        "SUPABASE_SERVICE_ROLE_KEY",
        "OPENAI_API_KEY",
        "WEBHOOK_SECRET_KEY",
        "JWT_SECRET_KEY"
    ]
    
    PLATFORM_SECRETS = [
        "INSTAGRAM_APP_SECRET",
        "TWITTER_CONSUMER_SECRET", 
        "YOUTUBE_CLIENT_SECRET",
        "LINKEDIN_CLIENT_SECRET"
    ]
    
    def validate_startup_config(self) -> None:
        """Validate all required configuration on startup"""
        try:
            config = get_config()
            
            # Check critical secrets
            missing_critical = self._check_critical_secrets(config)
            if missing_critical:
                self._abort_startup(f"CRITICAL: Missing required secrets: {', '.join(missing_critical)}")
                return
            
            # Check platform secrets
            missing_platform = self._check_platform_secrets(config)
            if missing_platform:
                self._abort_startup(f"CRITICAL: Missing platform secrets: {', '.join(missing_platform)}")
                return
            
            # Validate secret formats
            self._validate_secret_formats(config)
            
            logger.info("✅ All configuration validation passed")
            
        except Exception as e:
            self._abort_startup(f"Configuration validation failed: {str(e)}")
    
    def _check_critical_secrets(self, config) -> List[str]:
        """Check critical secrets are present"""
        missing = []
        for secret in self.CRITICAL_SECRETS:
            value = getattr(config, secret.lower(), None)
            if not value or len(value.strip()) == 0:
                missing.append(secret)
        return missing
    
    def _check_platform_secrets(self, config) -> List[str]:
        """Check platform secrets are present"""
        missing = []
        for secret in self.PLATFORM_SECRETS:
            value = getattr(config, secret.lower(), None)
            if not value or len(value.strip()) == 0:
                missing.append(secret)
        return missing
    
    def _validate_secret_formats(self, config) -> None:
        """Validate secret formats"""
        if not config.openai_api_key.startswith('sk-'):
            raise ValueError("OPENAI_API_KEY must start with 'sk-'")
        
        if not config.supabase_url.startswith('https://'):
            raise ValueError("SUPABASE_URL must be a valid HTTPS URL")
        
        if len(config.webhook_secret_key) < 32:
            raise ValueError("WEBHOOK_SECRET_KEY must be at least 32 characters")
        
        if len(config.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
    
    def _abort_startup(self, message: str) -> None:
        """Abort application startup with error message"""
        logger.error(f"🚨 STARTUP ABORTED: {message}")
        sys.exit(1)


def validate_config_on_startup() -> None:
    """Entry point for startup config validation"""
    bootstrap = ConfigBootstrap()
    bootstrap.validate_startup_config()


# CLI script for ops validation
if __name__ == "__main__":
    print("🔍 Validating PulsePilot configuration...")
    try:
        validate_config_on_startup()
        print("✅ All configuration is valid!")
    except SystemExit:
        print("❌ Configuration validation failed!")
        sys.exit(1)
