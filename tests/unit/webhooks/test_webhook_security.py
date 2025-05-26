"""
Unit tests for webhook security - critical for preventing unauthorized access
"""

import pytest
import hmac
import hashlib
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException, Request

from utils.webhook_security import WebhookSecurityManager


class TestWebhookSecurityManager:
    """Test webhook signature verification for all platforms"""

    @pytest.fixture
    def security_manager(self, mock_config):
        with patch('utils.webhook_security.get_config', return_value=mock_config):
            return WebhookSecurityManager()

    @pytest.fixture
    def mock_request(self):
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test-agent"}
        return request

    @pytest.mark.asyncio
    async def test_verify_webhook_instagram_valid_signature(self, security_manager, mock_request):
        """
        Business Critical: Valid Instagram signatures must be accepted to process webhooks
        """
        body = b'{"test": "data"}'
        secret = "test-instagram-secret"
        
        # Generate valid signature
        signature = "sha256=" + hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        headers = {"x-hub-signature-256": signature}
        
        is_valid = await security_manager.verify_webhook("instagram", mock_request, body, headers)
        
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_webhook_instagram_invalid_signature(self, security_manager, mock_request):
        """
        Business Critical: Invalid signatures must be rejected to prevent unauthorized access
        """
        body = b'{"test": "data"}'
        headers = {"x-hub-signature-256": "sha256=invalid_signature"}
        
        is_valid = await security_manager.verify_webhook("instagram", mock_request, body, headers)
        
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_webhook_instagram_missing_signature(self, security_manager, mock_request):
        """
        Business Critical: Missing signatures must be rejected
        """
        body = b'{"test": "data"}'
        headers = {}
        
        is_valid = await security_manager.verify_webhook("instagram", mock_request, body, headers)
        
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_webhook_twitter_valid_signature(self, security_manager, mock_request):
        """
        Business Critical: Valid Twitter signatures must be accepted
        """
        body = b'{"test": "data"}'
        secret = "test-twitter-secret"
        
        signature = "sha256=" + hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        headers = {"x-twitter-webhooks-signature": signature}
        
        is_valid = await security_manager.verify_webhook("twitter", mock_request, body, headers)
        
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_webhook_unsupported_platform(self, security_manager, mock_request):
        """
        Business Critical: Unsupported platforms should raise clear error
        """
        body = b'{"test": "data"}'
        headers = {}
        
        with pytest.raises(HTTPException) as exc_info:
            await security_manager.verify_webhook("unsupported", mock_request, body, headers)
        
        assert exc_info.value.status_code == 400
        assert "Unsupported platform" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_verify_webhook_missing_secret_config(self, mock_request):
        """
        Business Critical: Missing platform secrets should be handled gracefully
        """
        # Create config with missing Instagram secret
        mock_config = MagicMock()
        mock_config.instagram_app_secret = None
        
        with patch('utils.webhook_security.get_config', return_value=mock_config):
            security_manager = WebhookSecurityManager()
            
            body = b'{"test": "data"}'
            headers = {"x-hub-signature-256": "sha256=test"}
            
            is_valid = await security_manager.verify_webhook("instagram", mock_request, body, headers)
            
            assert is_valid is False

    @pytest.mark.asyncio
    async def test_handle_facebook_challenge_valid(self, security_manager, mock_request):
        """
        Business Critical: Valid Facebook webhook challenges must be handled correctly
        """
        mock_request.query_params = {
            "hub.mode": "subscribe",
            "hub.challenge": "12345",
            "hub.verify_token": "test-webhook-"  # First 16 chars of webhook secret
        }
        
        result = await security_manager.handle_webhook_challenge("instagram", mock_request)
        
        assert result == 12345

    @pytest.mark.asyncio
    async def test_handle_facebook_challenge_invalid_token(self, security_manager, mock_request):
        """
        Business Critical: Invalid verify tokens must be rejected
        """
        mock_request.query_params = {
            "hub.mode": "subscribe",
            "hub.challenge": "12345",
            "hub.verify_token": "invalid_token"
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await security_manager.handle_webhook_challenge("instagram", mock_request)
        
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_handle_twitter_crc_challenge(self, security_manager, mock_request):
        """
        Business Critical: Twitter CRC challenges must generate correct response
        """
        mock_request.query_params = {"crc_token": "test_token"}
        
        result = await security_manager.handle_webhook_challenge("twitter", mock_request)
        
        assert "response_token" in result
        assert result["response_token"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_handle_twitter_crc_missing_token(self, security_manager, mock_request):
        """
        Business Critical: Missing CRC token should raise error
        """
        mock_request.query_params = {}
        
        with pytest.raises(HTTPException) as exc_info:
            await security_manager.handle_webhook_challenge("twitter", mock_request)
        
        assert exc_info.value.status_code == 400
        assert "Missing crc_token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_log_security_event_success(self, security_manager, mock_request):
        """
        Business Critical: Security events must be logged for monitoring
        """
        with patch('utils.webhook_security.logger') as mock_logger, \
             patch('utils.webhook_security.track_webhook_metrics') as mock_metrics:
            
            await security_manager.log_security_event(
                platform="instagram",
                event_type="signature_verification",
                request=mock_request,
                success=True,
                details={"test": "data"}
            )
            
            mock_logger.info.assert_called_once()
            mock_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_security_event_failure(self, security_manager, mock_request):
        """
        Business Critical: Security failures must be logged as warnings
        """
        with patch('utils.webhook_security.logger') as mock_logger, \
             patch('utils.webhook_security.track_webhook_metrics') as mock_metrics:
            
            await security_manager.log_security_event(
                platform="instagram",
                event_type="signature_verification",
                request=mock_request,
                success=False
            )
            
            mock_logger.warning.assert_called_once()
            mock_metrics.assert_called_once()
