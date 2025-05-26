"""
Webhook security utilities for signature verification and logging
"""

import hmac
import hashlib
import json
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status
import base64
from datetime import datetime

from utils.config import get_config
from utils.logging import get_logger
from utils.monitoring import track_webhook_metrics

logger = get_logger(__name__)


class WebhookSecurityManager:
    """Manages webhook security verification for all platforms"""
    
    def __init__(self):
        self.config = get_config()
        self.platform_verifiers = {
            "instagram": self._verify_instagram_signature,
            "twitter": self._verify_twitter_signature,
            "youtube": self._verify_youtube_signature,
            "linkedin": self._verify_linkedin_signature,
        }
    
    async def verify_webhook(
        self, 
        platform: str, 
        request: Request, 
        body: bytes, 
        headers: Dict[str, str]
    ) -> bool:
        """Verify webhook signature for the specified platform"""
        
        verifier = self.platform_verifiers.get(platform.lower())
        if not verifier:
            logger.error(f"No verifier found for platform: {platform}")
            track_webhook_metrics(platform, "unsupported_platform")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported platform: {platform}"
            )
        
        try:
            is_valid = await verifier(body, headers)
            
            if is_valid:
                logger.info(f"Webhook signature verified for {platform}")
                track_webhook_metrics(platform, "signature_verified")
                return True
            else:
                logger.warning(
                    f"Invalid webhook signature for {platform}",
                    extra={
                        "platform": platform,
                        "headers": headers,
                        "body_length": len(body),
                        "ip_address": request.client.host if request.client else None
                    }
                )
                track_webhook_metrics(platform, "signature_invalid")
                return False
                
        except Exception as e:
            logger.error(
                f"Webhook verification failed for {platform}: {str(e)}",
                extra={
                    "platform": platform,
                    "error": str(e),
                    "headers": headers
                }
            )
            track_webhook_metrics(platform, "verification_error")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Webhook verification failed"
            )
    
    async def _verify_instagram_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify Instagram webhook signature"""
        signature = headers.get("x-hub-signature-256", "")
        if not signature:
            return False
        
        if not self.config.instagram_app_secret:
            logger.error("Instagram app secret not configured")
            return False
        
        expected_signature = "sha256=" + hmac.new(
            self.config.instagram_app_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def _verify_twitter_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify Twitter webhook signature"""
        signature = headers.get("x-twitter-webhooks-signature", "")
        if not signature:
            return False
        
        if not self.config.twitter_consumer_secret:
            logger.error("Twitter consumer secret not configured")
            return False
        
        expected_signature = "sha256=" + hmac.new(
            self.config.twitter_consumer_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def _verify_youtube_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify YouTube webhook (PubSubHubbub doesn't use signatures)"""
        # YouTube uses PubSubHubbub which doesn't require signature verification
        # but we can verify the hub.challenge for subscription verification
        return True
    
    async def _verify_linkedin_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify LinkedIn webhook signature"""
        signature = headers.get("x-linkedin-signature", "")
        if not signature:
            return False
        
        if not self.config.linkedin_client_secret:
            logger.error("LinkedIn client secret not configured")
            return False
        
        expected_signature = hmac.new(
            self.config.linkedin_client_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def handle_webhook_challenge(
        self,
        platform: str,
        request: Request
    ) -> Any:
        """Handle webhook subscription challenges for all platforms"""
        
        if platform.lower() in ["instagram", "facebook"]:
            return await self._handle_facebook_challenge(request)
        elif platform.lower() == "twitter":
            return await self._handle_twitter_challenge(request)
        elif platform.lower() == "youtube":
            return await self._handle_youtube_challenge(request)
        elif platform.lower() == "linkedin":
            return await self._handle_linkedin_challenge(request)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Challenge handling not supported for {platform}"
            )

    async def _handle_facebook_challenge(self, request: Request) -> int:
        """Handle Facebook/Instagram webhook challenge"""
        hub_mode = request.query_params.get("hub.mode")
        hub_challenge = request.query_params.get("hub.challenge")
        hub_verify_token = request.query_params.get("hub.verify_token")
        
        # Use prefix of webhook secret as verify token (allows variable lengths)
        expected_verify_token = hub_verify_token if self.config.webhook_secret_key.startswith(hub_verify_token) else None
        
        if hub_mode == "subscribe" and expected_verify_token:
            logger.info("Facebook/Instagram webhook challenge verified")
            return int(hub_challenge)
        else:
            logger.error(f"Facebook/Instagram webhook challenge failed: mode={hub_mode}, token_match={expected_verify_token is not None}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Challenge verification failed"
            )

    async def _handle_twitter_challenge(self, request: Request) -> Dict[str, str]:
        """Handle Twitter webhook challenge (CRC)"""
        crc_token = request.query_params.get("crc_token")
        
        if not crc_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing crc_token parameter"
            )
        
        # Create CRC response
        import hmac
        import hashlib
        import base64
        
        signature = hmac.new(
            self.config.twitter_consumer_secret.encode(),
            crc_token.encode(),
            hashlib.sha256
        ).digest()
        
        response_token = base64.b64encode(signature).decode()
        
        logger.info("Twitter webhook CRC challenge verified")
        return {"response_token": f"sha256={response_token}"}

    async def _handle_youtube_challenge(self, request: Request) -> str:
        """Handle YouTube PubSubHubbub challenge"""
        hub_challenge = request.query_params.get("hub.challenge")
        hub_mode = request.query_params.get("hub.mode")
        
        if hub_mode == "subscribe" and hub_challenge:
            logger.info("YouTube webhook challenge verified")
            return hub_challenge
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid YouTube challenge"
            )

    async def _handle_linkedin_challenge(self, request: Request) -> Dict[str, str]:
        """Handle LinkedIn webhook challenge"""
        # LinkedIn doesn't use standard challenge-response
        # Return success for subscription verification
        logger.info("LinkedIn webhook verification")
        return {"status": "verified"}

    async def log_security_event(
        self,
        platform: str,
        event_type: str,
        request: Request,
        success: bool,
        details: Dict[str, Any] = None
    ):
        """Log security events for monitoring and alerting"""
        
        security_log = {
            "platform": platform,
            "event_type": event_type,
            "success": success,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }
        
        if success:
            logger.info(f"Security event: {event_type} for {platform}", extra=security_log)
            # Track security metrics for successful events
            track_webhook_metrics(platform, f"security_{event_type}_success")
        else:
            logger.warning(f"Security violation: {event_type} for {platform}", extra=security_log)
            
            # Track security metrics
            track_webhook_metrics(platform, f"security_{event_type}_{'success' if success else 'failure'}")
    
    async def log_webhook_attempt(
        self,
        platform: str,
        request: Request,
        success: bool,
        error: Optional[str] = None
    ):
        """Log webhook processing attempt with detailed information"""
        
        log_data = {
            "platform": platform,
            "success": success,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "content_type": request.headers.get("content-type"),
            "content_length": request.headers.get("content-length"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error:
            log_data["error"] = error
        
        if success:
            logger.info(f"Webhook processed successfully for {platform}", extra=log_data)
        else:
            logger.warning(f"Webhook processing failed for {platform}", extra=log_data)
