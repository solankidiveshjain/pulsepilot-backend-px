"""
Webhook processors for different social media platforms
"""

import os
import hmac
import hashlib
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime

from models.database import Comment


class BaseWebhookProcessor(ABC):
    """Base class for webhook processors"""
    
    @abstractmethod
    async def verify_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify webhook signature"""
        pass
    
    @abstractmethod
    async def process_webhook(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process webhook payload and extract comments"""
        pass


class InstagramWebhookProcessor(BaseWebhookProcessor):
    """Instagram webhook processor"""
    
    async def verify_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify Instagram webhook signature"""
        signature = headers.get("x-hub-signature-256", "")
        if not signature:
            return False
        
        app_secret = os.getenv("INSTAGRAM_APP_SECRET")
        if not app_secret:
            return False
        
        expected_signature = "sha256=" + hmac.new(
            app_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def process_webhook(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process Instagram webhook payload"""
        comments = []
        
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") == "comments":
                    value = change.get("value", {})
                    
                    comment_data = {
                        "comment_id": str(uuid4()),
                        "platform": "instagram",
                        "external_id": value.get("id"),
                        "author": value.get("from", {}).get("username"),
                        "message": value.get("text"),
                        "post_id": value.get("media", {}).get("id"),
                        "metadata": {
                            "instagram_data": value,
                            "webhook_timestamp": datetime.utcnow().isoformat()
                        }
                    }
                    comments.append(comment_data)
        
        return comments


class TwitterWebhookProcessor(BaseWebhookProcessor):
    """Twitter webhook processor"""
    
    async def verify_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify Twitter webhook signature"""
        signature = headers.get("x-twitter-webhooks-signature", "")
        if not signature:
            return False
        
        consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
        if not consumer_secret:
            return False
        
        expected_signature = "sha256=" + hmac.new(
            consumer_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def process_webhook(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process Twitter webhook payload"""
        comments = []
        
        # Handle tweet replies
        for tweet in payload.get("tweet_create_events", []):
            if tweet.get("in_reply_to_status_id"):
                comment_data = {
                    "comment_id": str(uuid4()),
                    "platform": "twitter",
                    "external_id": tweet.get("id_str"),
                    "author": tweet.get("user", {}).get("screen_name"),
                    "message": tweet.get("text"),
                    "post_id": tweet.get("in_reply_to_status_id"),
                    "metadata": {
                        "twitter_data": tweet,
                        "webhook_timestamp": datetime.utcnow().isoformat()
                    }
                }
                comments.append(comment_data)
        
        return comments


class YouTubeWebhookProcessor(BaseWebhookProcessor):
    """YouTube webhook processor"""
    
    async def verify_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify YouTube webhook signature"""
        # YouTube uses PubSubHubbub which doesn't require signature verification
        # but we can verify the challenge parameter for subscription verification
        return True
    
    async def process_webhook(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process YouTube webhook payload"""
        comments = []
        
        # YouTube webhooks are XML-based, this is a simplified JSON example
        if "comment" in payload:
            comment_data = {
                "comment_id": str(uuid4()),
                "platform": "youtube",
                "external_id": payload.get("comment", {}).get("id"),
                "author": payload.get("comment", {}).get("authorDisplayName"),
                "message": payload.get("comment", {}).get("textDisplay"),
                "post_id": payload.get("comment", {}).get("videoId"),
                "metadata": {
                    "youtube_data": payload,
                    "webhook_timestamp": datetime.utcnow().isoformat()
                }
            }
            comments.append(comment_data)
        
        return comments


class LinkedInWebhookProcessor(BaseWebhookProcessor):
    """LinkedIn webhook processor"""
    
    async def verify_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify LinkedIn webhook signature"""
        signature = headers.get("x-linkedin-signature", "")
        if not signature:
            return False
        
        client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
        if not client_secret:
            return False
        
        expected_signature = hmac.new(
            client_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def process_webhook(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process LinkedIn webhook payload"""
        comments = []
        
        for event in payload.get("events", []):
            if event.get("eventType") == "COMMENT_CREATED":
                comment_data = {
                    "comment_id": str(uuid4()),
                    "platform": "linkedin",
                    "external_id": event.get("comment", {}).get("id"),
                    "author": event.get("comment", {}).get("author"),
                    "message": event.get("comment", {}).get("message", {}).get("text"),
                    "post_id": event.get("comment", {}).get("object"),
                    "metadata": {
                        "linkedin_data": event,
                        "webhook_timestamp": datetime.utcnow().isoformat()
                    }
                }
                comments.append(comment_data)
        
        return comments


# Webhook processor registry
WEBHOOK_PROCESSORS = {
    "instagram": InstagramWebhookProcessor,
    "twitter": TwitterWebhookProcessor,
    "youtube": YouTubeWebhookProcessor,
    "linkedin": LinkedInWebhookProcessor
}


def get_webhook_processor(platform: str) -> Optional[BaseWebhookProcessor]:
    """Get webhook processor instance"""
    processor_class = WEBHOOK_PROCESSORS.get(platform.lower())
    if processor_class:
        return processor_class()
    return None
