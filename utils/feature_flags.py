"""
Feature flag and settings registry
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum

from utils.config import get_config
from utils.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)


class FeatureFlag(str, Enum):
    """Available feature flags"""
    
    # AI/ML Features
    ENABLE_RAG_SUGGESTIONS = "enable_rag_suggestions"
    ENABLE_SENTIMENT_ANALYSIS = "enable_sentiment_analysis"
    ENABLE_AUTO_MODERATION = "enable_auto_moderation"
    
    # Platform Features
    ENABLE_BULK_REPLIES = "enable_bulk_replies"
    ENABLE_SCHEDULED_REPLIES = "enable_scheduled_replies"
    ENABLE_REPLY_TEMPLATES = "enable_reply_templates"
    
    # Performance Features
    ENABLE_RESPONSE_CACHING = "enable_response_caching"
    ENABLE_BATCH_PROCESSING = "enable_batch_processing"
    ENABLE_ASYNC_WEBHOOKS = "enable_async_webhooks"
    
    # Monitoring Features
    ENABLE_DETAILED_METRICS = "enable_detailed_metrics"
    ENABLE_ERROR_TRACKING = "enable_error_tracking"
    ENABLE_PERFORMANCE_PROFILING = "enable_performance_profiling"


class FeatureFlagConfig(BaseModel):
    """Feature flag configuration model"""
    
    # AI/ML Features
    enable_rag_suggestions: bool = Field(True, description="Enable RAG-based suggestions")
    enable_sentiment_analysis: bool = Field(True, description="Enable sentiment analysis")
    enable_auto_moderation: bool = Field(False, description="Enable auto-moderation")
    
    # Platform Features
    enable_bulk_replies: bool = Field(True, description="Enable bulk reply operations")
    enable_scheduled_replies: bool = Field(False, description="Enable scheduled replies")
    enable_reply_templates: bool = Field(True, description="Enable reply templates")
    
    # Performance Features
    enable_response_caching: bool = Field(True, description="Enable response caching")
    enable_batch_processing: bool = Field(True, description="Enable batch processing")
    enable_async_webhooks: bool = Field(True, description="Enable async webhook processing")
    
    # Monitoring Features
    enable_detailed_metrics: bool = Field(True, description="Enable detailed metrics")
    enable_error_tracking: bool = Field(True, description="Enable error tracking")
    enable_performance_profiling: bool = Field(False, description="Enable performance profiling")


class SettingsRegistry:
    """Registry for application settings and feature flags"""
    
    def __init__(self):
        """Initialize settings registry"""
        self.config = get_config()
        self.feature_flags = self._load_feature_flags()
        self.settings = self._load_settings()
    
    def _load_feature_flags(self) -> FeatureFlagConfig:
        """
        Load feature flags from environment or defaults
        
        Returns:
            Feature flag configuration
        """
        import os
        
        flag_values = {}
        for flag in FeatureFlag:
            env_var = f"FEATURE_{flag.value.upper()}"
            env_value = os.getenv(env_var)
            
            if env_value is not None:
                flag_values[flag.value] = env_value.lower() in ('true', '1', 'yes', 'on')
        
        return FeatureFlagConfig(**flag_values)
    
    def _load_settings(self) -> Dict[str, Any]:
        """
        Load application settings
        
        Returns:
            Settings dictionary
        """
        return {
            # Rate limiting settings
            "rate_limit_enabled": True,
            "rate_limit_requests_per_minute": 100,
            
            # LLM settings
            "llm_max_tokens": 4000,
            "llm_temperature": 0.7,
            "llm_timeout_seconds": 30,
            
            # Vector search settings
            "vector_similarity_threshold": 0.7,
            "vector_max_results": 10,
            
            # Webhook settings
            "webhook_timeout_seconds": 30,
            "webhook_retry_attempts": 3,
            "webhook_deduplication_hours": 24,
            
            # Task queue settings
            "task_queue_max_retries": 3,
            "task_queue_retry_delay_seconds": 60,
            
            # Billing settings
            "billing_quota_check_enabled": True,
            "billing_quota_warning_threshold": 0.8,
        }
    
    def is_enabled(self, flag: FeatureFlag) -> bool:
        """
        Check if feature flag is enabled
        
        Args:
            flag: Feature flag to check
            
        Returns:
            True if feature is enabled
        """
        return getattr(self.feature_flags, flag.value, False)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get application setting value
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        return self.settings.get(key, default)
    
    def update_feature_flag(self, flag: FeatureFlag, enabled: bool) -> None:
        """
        Update feature flag value (runtime override)
        
        Args:
            flag: Feature flag to update
            enabled: New enabled state
        """
        setattr(self.feature_flags, flag.value, enabled)
        logger.info("Feature flag updated",
                   flag=flag.value,
                   enabled=enabled)
    
    def get_all_flags(self) -> Dict[str, bool]:
        """
        Get all feature flag states
        
        Returns:
            Dictionary of flag states
        """
        return self.feature_flags.dict()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all application settings
        
        Returns:
            Dictionary of settings
        """
        return self.settings.copy()


# Global settings registry
settings_registry = SettingsRegistry()


def is_feature_enabled(flag: FeatureFlag) -> bool:
    """
    Helper function to check feature flag
    
    Args:
        flag: Feature flag to check
        
    Returns:
        True if feature is enabled
    """
    return settings_registry.is_enabled(flag)


def get_setting(key: str, default: Any = None) -> Any:
    """
    Helper function to get setting value
    
    Args:
        key: Setting key
        default: Default value
        
    Returns:
        Setting value or default
    """
    return settings_registry.get_setting(key, default)
