"""
Unit tests for configuration bootstrap - critical for preventing startup with invalid config
"""

import pytest
from unittest.mock import patch, MagicMock
import sys

from utils.config_bootstrap import ConfigBootstrap, validate_config_on_startup


class TestConfigBootstrap:
    """Test fail-fast configuration validation"""

    @pytest.fixture
    def bootstrap(self):
        return ConfigBootstrap()

    @pytest.fixture
    def valid_config(self):
        config = MagicMock()
        config.postgres_url = "postgresql://user:pass@localhost/db"
        config.supabase_url = "https://test.supabase.co"
        config.supabase_jwt_secret = "test-jwt-secret-32-chars-long-123"
        config.supabase_service_role_key = "test-service-role-key"
        config.openai_api_key = "sk-test-openai-key"
        config.webhook_secret_key = "test-webhook-secret-32-chars-long"
        config.jwt_secret_key = "test-jwt-secret-32-chars-long-456"
        config.instagram_app_secret = "test-instagram-secret"
        config.twitter_consumer_secret = "test-twitter-secret"
        config.youtube_client_secret = "test-youtube-secret"
        config.linkedin_client_secret = "test-linkedin-secret"
        return config

    def test_validate_startup_config_success(self, bootstrap, valid_config):
        """
        Business Critical: Valid configuration should pass validation without errors
        """
        with patch('utils.config_bootstrap.get_config', return_value=valid_config), \
             patch('utils.config_bootstrap.logger') as mock_logger:
            
            # Should not raise any exception
            bootstrap.validate_startup_config()
            
            mock_logger.info.assert_called_with("✅ All configuration validation passed")

    def test_validate_startup_config_missing_critical_secret_aborts(self, bootstrap):
        """
        Business Critical: Missing critical secrets must abort startup to prevent runtime failures
        """
        config = MagicMock()
        config.postgres_url = ""  # Missing critical secret
        config.supabase_url = "https://test.supabase.co"
        config.supabase_jwt_secret = "test-jwt-secret"
        config.supabase_service_role_key = "test-service-role-key"
        config.openai_api_key = "sk-test-key"
        config.webhook_secret_key = "test-webhook-secret-32-chars-long"
        config.jwt_secret_key = "test-jwt-secret-32-chars-long-456"
        
        with patch('utils.config_bootstrap.get_config', return_value=config), \
             patch.object(bootstrap, '_abort_startup') as mock_abort:
            
            bootstrap.validate_startup_config()
            
            mock_abort.assert_called_once()
            assert "CRITICAL: Missing required secrets" in mock_abort.call_args[0][0]
            assert "POSTGRES_URL" in mock_abort.call_args[0][0]

    def test_validate_startup_config_missing_platform_secret_aborts(self, bootstrap, valid_config):
        """
        Business Critical: Missing platform secrets must abort startup to prevent webhook failures
        """
        valid_config.instagram_app_secret = ""  # Missing platform secret
        
        with patch('utils.config_bootstrap.get_config', return_value=valid_config), \
             patch.object(bootstrap, '_abort_startup') as mock_abort:
            
            bootstrap.validate_startup_config()
            
            mock_abort.assert_called_once()
            assert "CRITICAL: Missing platform secrets" in mock_abort.call_args[0][0]
            assert "INSTAGRAM_APP_SECRET" in mock_abort.call_args[0][0]

    def test_validate_startup_config_invalid_openai_key_format(self, bootstrap, valid_config):
        """
        Business Critical: Invalid OpenAI key format must be detected to prevent API failures
        """
        valid_config.openai_api_key = "invalid-key-format"  # Should start with 'sk-'
        
        with patch('utils.config_bootstrap.get_config', return_value=valid_config), \
             patch.object(bootstrap, '_abort_startup') as mock_abort:
            
            bootstrap.validate_startup_config()
            
            mock_abort.assert_called_once()
            assert "OPENAI_API_KEY must start with 'sk-'" in mock_abort.call_args[0][0]

    def test_validate_startup_config_invalid_supabase_url(self, bootstrap, valid_config):
        """
        Business Critical: Invalid Supabase URL must be detected to prevent connection failures
        """
        valid_config.supabase_url = "http://invalid-url"  # Should be HTTPS
        
        with patch('utils.config_bootstrap.get_config', return_value=valid_config), \
             patch.object(bootstrap, '_abort_startup') as mock_abort:
            
            bootstrap.validate_startup_config()
            
            mock_abort.assert_called_once()
            assert "SUPABASE_URL must be a valid HTTPS URL" in mock_abort.call_args[0][0]

    def test_validate_startup_config_short_webhook_secret(self, bootstrap, valid_config):
        """
        Business Critical: Short webhook secrets must be rejected for security
        """
        valid_config.webhook_secret_key = "short"  # Less than 32 characters
        
        with patch('utils.config_bootstrap.get_config', return_value=valid_config), \
             patch.object(bootstrap, '_abort_startup') as mock_abort:
            
            bootstrap.validate_startup_config()
            
            mock_abort.assert_called_once()
            assert "WEBHOOK_SECRET_KEY must be at least 32 characters" in mock_abort.call_args[0][0]

    def test_validate_startup_config_short_jwt_secret(self, bootstrap, valid_config):
        """
        Business Critical: Short JWT secrets must be rejected for security
        """
        valid_config.jwt_secret_key = "short"  # Less than 32 characters
        
        with patch('utils.config_bootstrap.get_config', return_value=valid_config), \
             patch.object(bootstrap, '_abort_startup') as mock_abort:
            
            bootstrap.validate_startup_config()
            
            mock_abort.assert_called_once()
            assert "JWT_SECRET_KEY must be at least 32 characters" in mock_abort.call_args[0][0]

    def test_check_critical_secrets_identifies_missing(self, bootstrap):
        """
        Business Critical: All critical secrets must be identified when missing
        """
        config = MagicMock()
        # Set all to empty/None
        for secret in bootstrap.CRITICAL_SECRETS:
            setattr(config, secret.lower(), "")
        
        missing = bootstrap._check_critical_secrets(config)
        
        assert len(missing) == len(bootstrap.CRITICAL_SECRETS)
        assert set(missing) == set(bootstrap.CRITICAL_SECRETS)

    def test_check_critical_secrets_handles_none_values(self, bootstrap):
        """
        Business Critical: None values should be treated as missing secrets
        """
        config = MagicMock()
        config.postgres_url = None
        config.supabase_url = "https://test.supabase.co"
        config.supabase_jwt_secret = "test-secret"
        config.supabase_service_role_key = "test-key"
        config.openai_api_key = "sk-test"
        config.webhook_secret_key = "test-webhook-secret-32-chars-long"
        config.jwt_secret_key = "test-jwt-secret-32-chars-long-456"
        
        missing = bootstrap._check_critical_secrets(config)
        
        assert "POSTGRES_URL" in missing

    def test_check_platform_secrets_identifies_missing(self, bootstrap):
        """
        Business Critical: All platform secrets must be identified when missing
        """
        config = MagicMock()
        # Set all to empty
        for secret in bootstrap.PLATFORM_SECRETS:
            setattr(config, secret.lower(), "")
        
        missing = bootstrap._check_platform_secrets(config)
        
        assert len(missing) == len(bootstrap.PLATFORM_SECRETS)
        assert set(missing) == set(bootstrap.PLATFORM_SECRETS)

    def test_abort_startup_exits_with_error(self, bootstrap):
        """
        Business Critical: Startup abort must exit the process to prevent invalid startup
        """
        with patch('utils.config_bootstrap.logger') as mock_logger, \
             patch('sys.exit') as mock_exit:
            
            bootstrap._abort_startup("Test error message")
            
            mock_logger.error.assert_called_once()
            mock_exit.assert_called_once_with(1)

    def test_validate_config_on_startup_entry_point(self, valid_config):
        """
        Business Critical: Entry point function must work correctly for application startup
        """
        with patch('utils.config_bootstrap.get_config', return_value=valid_config), \
             patch('utils.config_bootstrap.logger'):
            
            # Should not raise any exception
            validate_config_on_startup()

    def test_validate_config_on_startup_handles_system_exit(self):
        """
        Business Critical: SystemExit from validation should be handled properly
        """
        with patch('utils.config_bootstrap.ConfigBootstrap') as mock_bootstrap_class:
            mock_bootstrap = MagicMock()
            mock_bootstrap.validate_startup_config.side_effect = SystemExit(1)
            mock_bootstrap_class.return_value = mock_bootstrap
            
            with pytest.raises(SystemExit):
                validate_config_on_startup()
