"""
Webhook endpoints for ingesting comments from social platforms - Refactored
"""

from fastapi import APIRouter, Request, HTTPException, status, BackgroundTasks
from services.platforms.registry import get_platform_service
from services.platforms.base import WebhookPayload
from tasks.webhook_tasks import webhook_processing_task, task_queue
from schemas.responses import WebhookResponse
from utils.exceptions import handle_platform_error

router = APIRouter()


@router.post("/{platform}", response_model=WebhookResponse)
async def handle_webhook(
    platform: str,
    request: Request,
    background_tasks: BackgroundTasks
) -> WebhookResponse:
    """Handle webhook from social media platform"""
    
    try:
        # Get platform service
        platform_service = get_platform_service(platform)
        
        # Get raw body and headers
        body = await request.body()
        headers = dict(request.headers)
        
        # Parse JSON payload
        try:
            json_data = await request.json()
        except Exception:
            json_data = {}
        
        # Prepare payload data for background task
        payload_data = {
            "headers": headers,
            "body": body,
            "json_data": json_data,
            "team_id": None  # This should be determined from webhook content
        }
        
        # Queue webhook processing task
        task_queue.add_task(
            webhook_processing_task.run_with_error_handling(platform, payload_data)
        )
        
        return WebhookResponse(
            status="accepted",
            message=f"Webhook from {platform} queued for processing"
        )
        
    except Exception as e:
        raise handle_platform_error(e, platform)
