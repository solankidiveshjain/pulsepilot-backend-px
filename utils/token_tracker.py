"""
Token usage tracking utility for billing
"""

from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import TokenUsage, Pricing, Subscription
from utils.database import get_session


class TokenTracker:
    """Utility for tracking token usage and calculating costs"""
    
    async def track_usage(
        self,
        team_id: UUID,
        usage_type: str,
        tokens_used: int,
        cost: float = None
    ) -> TokenUsage:
        """Track token usage for a team"""
        
        async with get_session() as db:
            # Calculate cost if not provided
            if cost is None:
                cost = await self._calculate_cost(usage_type, tokens_used, db)
            
            # Create usage record
            usage = TokenUsage(
                team_id=team_id,
                usage_type=usage_type,
                tokens_used=tokens_used,
                cost=cost
            )
            
            db.add(usage)
            await db.commit()
            await db.refresh(usage)
            
            return usage
    
    async def _calculate_cost(
        self,
        usage_type: str,
        tokens_used: int,
        db: AsyncSession
    ) -> float:
        """Calculate cost based on current pricing"""
        
        # Get current pricing
        stmt = select(Pricing).where(
            Pricing.usage_type == usage_type
        ).order_by(Pricing.effective_date.desc())
        
        result = await db.execute(stmt)
        pricing = result.scalar_one_or_none()
        
        if not pricing:
            # Default pricing if not found
            default_prices = {
                "embedding": 0.0001,
                "classification": 0.0002,
                "generation": 0.002
            }
            price_per_token = default_prices.get(usage_type, 0.001)
        else:
            price_per_token = pricing.price_per_token
        
        return tokens_used * price_per_token
    
    async def check_quota(self, team_id: UUID) -> dict:
        """Check team's token quota and usage"""
        
        async with get_session() as db:
            # Get active subscription
            stmt = select(Subscription).where(
                Subscription.team_id == team_id,
                Subscription.status == "active"
            )
            result = await db.execute(stmt)
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                return {
                    "has_quota": False,
                    "quota_limit": 0,
                    "tokens_used": 0,
                    "tokens_remaining": 0
                }
            
            # Calculate current month usage
            current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            stmt = select(TokenUsage).where(
                TokenUsage.team_id == team_id,
                TokenUsage.created_at >= current_month
            )
            result = await db.execute(stmt)
            usage_records = result.scalars().all()
            
            total_tokens_used = sum(record.tokens_used for record in usage_records)
            tokens_remaining = max(0, subscription.monthly_token_quota - total_tokens_used)
            
            return {
                "has_quota": True,
                "quota_limit": subscription.monthly_token_quota,
                "tokens_used": total_tokens_used,
                "tokens_remaining": tokens_remaining,
                "quota_exceeded": total_tokens_used > subscription.monthly_token_quota
            }
