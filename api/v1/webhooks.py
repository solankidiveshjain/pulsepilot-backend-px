"""
RESTful webhook endpoints with enhanced security
"""

from fastapi import APIRouter, Request, HTTPException, status, Depends
from utils.webhook_security import verify_and_parse_webhook
from utils.task_queue import task_queue
from schemas.responses import WebhookResponse
from utils.exceptions import handle_platform_error
from utils.logging import get_logger
from typing import Dict, Any

router = APIRouter()
logger = get_logger(__name__)


@router.post("/{platform}", response_model=WebhookResponse)
async def handle_platform_webhook(
    platform: str,
    payload_data: Dict[str, Any] = Depends(verify_and_parse_webhook)
) -> WebhookResponse:
    """Handle webhook from social media platform with strict validation and dispatch"""
    # Enqueue webhook processing
    payload_data['team_id'] = None  # Determine from payload if needed
    job_id = await task_queue.enqueue_webhook_processing(platform, payload_data)
    return WebhookResponse(
        status="accepted",
        message=f"Webhook from {platform} validated and queued",
        comments_processed=0,
        job_id=job_id
    )


@router.get("/{platform}/challenge")
async def handle_webhook_challenge(
    platform: str,
    request: Request
):
    """Handle webhook subscription challenges for all platforms"""
    
    try:
        response = await webhook_security.handle_webhook_challenge(platform, request)
        
        await webhook_security.log_security_event(
            platform=platform,
            event_type="challenge_verification",
            request=request,
            success=True
        )
        
        return response
        
    except Exception as e:
        await webhook_security.log_security_event(
            platform=platform,
            event_type="challenge_verification",
            request=request,
            success=False,
            details={"error": str(e)}
        )
        raise


async def _validate_webhook_payload(platform: str, json_data: Dict[str, Any]):
    """Validate webhook payload with platform-specific Pydantic models"""
    from schemas.webhook_schemas import (
        InstagramWebhookPayload,
        TwitterWebhookPayload,
        YouTubeWebhookPayload,
        LinkedInWebhookPayload
    )
    
    validators = {
        "instagram": InstagramWebhookPayload,
        "twitter": TwitterWebhookPayload,
        "youtube": YouTubeWebhookPayload,
        "linkedin": LinkedInWebhookPayload
    }
    
    validator_class = validators.get(platform.lower())
    if not validator_class:
        raise ValueError(f"No validator for platform: {platform}")
    
    return validator_class(**json_data)


@router.get("/{platform}/verify")
async def verify_webhook_subscription(
    platform: str,
    request: Request
):
    """Handle webhook subscription verification (for platforms that require it)"""
    
    # Handle Facebook/Instagram webhook verification
    if platform.lower() in ["instagram", "facebook"]:
        hub_mode = request.query_params.get("hub.mode")
        hub_challenge = request.query_params.get("hub.challenge")
        hub_verify_token = request.query_params.get("hub.verify_token")
        
        # Verify the token (you should set this in your platform configuration)
        expected_verify_token = "your_verify_token"  # This should come from config
        
        if hub_mode == "subscribe" and hub_verify_token == expected_verify_token:
            logger.info(f"Webhook subscription verified for {platform}")
            return int(hub_challenge)
        else:
            logger.warning(f"Webhook verification failed for {platform}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Verification failed"
            )
    
    return {"message": "Verification not required for this platform"}
