"""
Webhook endpoints for ingesting comments from social platforms
"""

from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, status, BackgroundTasks
from pydantic import BaseModel

from services.webhook_processors import get_webhook_processor
from tasks.comment_tasks import process_comment_embedding


router = APIRouter()


class WebhookResponse(BaseModel):
    status: str
    message: str


@router.post("/{platform}")
async def handle_webhook(
    platform: str,
    request: Request,
    background_tasks: BackgroundTasks
) -> WebhookResponse:
    """Handle webhook from social media platform"""
    
    # Get webhook processor for platform
    processor = get_webhook_processor(platform)
    if not processor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: {platform}"
        )
    
    try:
        # Get raw body and headers
        body = await request.body()
        headers = dict(request.headers)
        
        # Verify webhook signature
        is_valid = await processor.verify_signature(body, headers)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Parse webhook payload
        payload = await request.json()
        
        # Process webhook and extract comments
        comments = await processor.process_webhook(payload)
        
        # Queue background tasks for each comment
        for comment_data in comments:
            background_tasks.add_task(
                process_comment_embedding,
                comment_data
            )
        
        return WebhookResponse(
            status="success",
            message=f"Processed {len(comments)} comments from {platform}"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )
