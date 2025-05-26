"""
Webhook security utilities for signature verification and logging
"""

import hmac
import hashlib
import json
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status

from utils.config import get_config
from utils.logging import get_logger
from utils.monitoring import track_webhook_metrics

logger = get_logger(__name__)
config = get_config()


class WebhookSecurityManager:
    """Manages webhook security verification for all platforms"""
    
    def __init__(self):
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
        
        if not config.instagram_app_secret:
            logger.error("Instagram app secret not configured")
            return False
        
        expected_signature = "sha256=" + hmac.new(
            config.instagram_app_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def _verify_twitter_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify Twitter webhook signature"""
        signature = headers.get("x-twitter-webhooks-signature", "")
        if not signature:
            return False
        
        if not config.twitter_consumer_secret:
            logger.error("Twitter consumer secret not configured")
            return False
        
        expected_signature = "sha256=" + hmac.new(
            config.twitter_consumer_secret.encode(),
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
        
        if not config.linkedin_client_secret:
            logger.error("LinkedIn client secret not configured")
            return False
        
        expected_signature = hmac.new(
            config.linkedin_client_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
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


# Global webhook security manager
webhook_security = WebhookSecurityManager()
