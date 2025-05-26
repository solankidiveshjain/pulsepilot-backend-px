"""
RESTful webhook endpoints with enhanced security
"""

from fastapi import APIRouter, Request, HTTPException, status, Depends
from utils.webhook_security import webhook_security
from utils.task_queue import task_queue
from schemas.responses import WebhookResponse
from utils.exceptions import handle_platform_error
from utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/{platform}", response_model=WebhookResponse)
async def handle_platform_webhook(
    platform: str,
    request: Request
) -> WebhookResponse:
    """Handle webhook from social media platform with security verification"""
    
    try:
        # Get raw body and headers
        body = await request.body()
        headers = dict(request.headers)
        
        # Verify webhook signature
        is_valid = await webhook_security.verify_webhook(platform, request, body, headers)
        
        if not is_valid:
            await webhook_security.log_webhook_attempt(platform, request, False, "Invalid signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Parse JSON payload
        try:
            json_data = await request.json()
        except Exception as e:
            await webhook_security.log_webhook_attempt(platform, request, False, f"Invalid JSON: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload"
            )
        
        # Prepare payload data for background processing
        payload_data = {
            "headers": headers,
            "body": body,
            "json_data": json_data,
            "team_id": None  # This should be determined from webhook content
        }
        
        # Enqueue webhook processing
        job_id = await task_queue.enqueue_webhook_processing(platform, payload_data)
        
        await webhook_security.log_webhook_attempt(platform, request, True)
        
        return WebhookResponse(
            status="accepted",
            message=f"Webhook from {platform} queued for processing",
            comments_processed=0,  # Will be updated by background job
            job_id=job_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await webhook_security.log_webhook_attempt(platform, request, False, str(e))
        raise handle_platform_error(e, platform)


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
