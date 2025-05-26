"""
Enhanced token usage tracking utility for billing with LLM integration
"""

from uuid import UUID
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.database import TokenUsage, Pricing, Subscription
from utils.database import get_session
from utils.logging import get_logger

logger = get_logger(__name__)


class TokenTracker:
    """Enhanced utility for tracking token usage and calculating costs"""
    
    async def track_usage(
        self,
        team_id: UUID,
        usage_type: str,
        tokens_used: int,
        cost: float = None,
        metadata: Dict[str, Any] = None
    ) -> TokenUsage:
        """Track token usage for a team with enhanced metadata"""
        
        async with get_session() as db:
            # Calculate cost if not provided
            if cost is None:
                cost = await self._calculate_cost(usage_type, tokens_used, db)
            
            # Create usage record with metadata
            usage = TokenUsage(
                team_id=team_id,
                usage_type=usage_type,
                tokens_used=tokens_used,
                cost=cost,
                metadata=metadata or {}
            )
            
            db.add(usage)
            await db.commit()
            await db.refresh(usage)
            
            # Quota check is omitted during usage tracking to avoid asynchronous issues
            
            return usage
    
    async def track_llm_usage(
        self,
        team_id: UUID,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        operation: str = "generation"
    ) -> TokenUsage:
        """Track LLM-specific usage with detailed breakdown"""
        
        # Calculate cost based on model pricing
        cost = await self._calculate_llm_cost(model_name, prompt_tokens, completion_tokens)
        
        metadata = {
            "model_name": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return await self.track_usage(
            team_id=team_id,
            usage_type="generation",
            tokens_used=total_tokens,
            cost=cost,
            metadata=metadata
        )
    
    async def track_embedding_usage(
        self,
        team_id: UUID,
        text_length: int,
        embedding_model: str = "all-MiniLM-L6-v2"
    ) -> TokenUsage:
        """Track embedding generation usage"""
        
        # Estimate tokens (rough approximation)
        estimated_tokens = max(1, text_length // 4)
        
        metadata = {
            "embedding_model": embedding_model,
            "text_length": text_length,
            "estimated_tokens": estimated_tokens,
            "operation": "embedding_generation"
        }
        
        return await self.track_usage(
            team_id=team_id,
            usage_type="embedding",
            tokens_used=estimated_tokens,
            metadata=metadata
        )
    
    async def track_classification_usage(
        self,
        team_id: UUID,
        text_length: int,
        classification_types: list
    ) -> TokenUsage:
        """Track classification usage"""
        
        estimated_tokens = max(1, text_length // 4)
        
        metadata = {
            "text_length": text_length,
            "classification_types": classification_types,
            "estimated_tokens": estimated_tokens,
            "operation": "classification"
        }
        
        return await self.track_usage(
            team_id=team_id,
            usage_type="classification",
            tokens_used=estimated_tokens,
            metadata=metadata
        )
    
    async def _calculate_llm_cost(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Calculate cost for LLM usage based on model pricing"""
        
        # Model-specific pricing (per 1K tokens)
        model_pricing = {
            "gpt-4-turbo-preview": {"prompt": 0.01, "completion": 0.03},
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-3.5-turbo": {"prompt": 0.001, "completion": 0.002},
        }
        
        pricing = model_pricing.get(model_name, {"prompt": 0.01, "completion": 0.03})
        
        prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
        completion_cost = (completion_tokens / 1000) * pricing["completion"]
        
        return prompt_cost + completion_cost
    
    async def _calculate_cost(
        self,
        usage_type: str,
        tokens_used: int,
        db: AsyncSession
    ) -> float:
        """Calculate cost based on default pricing rates"""
        default_prices = {
            "embedding": 0.0001,
            "classification": 0.0002,
            "generation": 0.002
        }
        price_per_token = default_prices.get(usage_type, 0.001)
        return tokens_used * price_per_token
    
    async def check_quota(self, team_id: UUID) -> dict:
        """Check team's token quota and usage with detailed breakdown"""
        
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
                    "tokens_remaining": 0,
                    "usage_breakdown": {}
                }
            
            # Calculate current month usage
            current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Get usage breakdown by type
            stmt = select(
                TokenUsage.usage_type,
                func.sum(TokenUsage.tokens_used).label('total_tokens'),
                func.sum(TokenUsage.cost).label('total_cost'),
                func.count(TokenUsage.usage_id).label('usage_count')
            ).where(
                TokenUsage.team_id == team_id,
                TokenUsage.created_at >= current_month
            ).group_by(TokenUsage.usage_type)
            
            result = await db.execute(stmt)
            usage_breakdown = {}
            total_tokens_used = 0
            
            for row in result.fetchall():
                usage_breakdown[row.usage_type] = {
                    "tokens": int(row.total_tokens or 0),
                    "cost": float(row.total_cost or 0),
                    "count": int(row.usage_count or 0)
                }
                total_tokens_used += int(row.total_tokens or 0)
            
            tokens_remaining = max(0, subscription.monthly_token_quota - total_tokens_used)
            
            return {
                "has_quota": True,
                "quota_limit": subscription.monthly_token_quota,
                "tokens_used": total_tokens_used,
                "tokens_remaining": tokens_remaining,
                "quota_exceeded": total_tokens_used > subscription.monthly_token_quota,
                "usage_breakdown": usage_breakdown,
                "subscription_plan": subscription.plan
            }
    
    async def get_usage_analytics(self, team_id: UUID, days: int = 30) -> Dict[str, Any]:
        """Get detailed usage analytics for a team"""
        
        async with get_session() as db:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Daily usage trends
            stmt = select(
                func.date(TokenUsage.created_at).label('date'),
                TokenUsage.usage_type,
                func.sum(TokenUsage.tokens_used).label('tokens'),
                func.sum(TokenUsage.cost).label('cost')
            ).where(
                TokenUsage.team_id == team_id,
                TokenUsage.created_at >= start_date
            ).group_by(
                func.date(TokenUsage.created_at),
                TokenUsage.usage_type
            ).order_by(func.date(TokenUsage.created_at))
            
            result = await db.execute(stmt)
            daily_usage = {}
            
            for row in result.fetchall():
                date_str = row.date.isoformat()
                if date_str not in daily_usage:
                    daily_usage[date_str] = {}
                
                daily_usage[date_str][row.usage_type] = {
                    "tokens": int(row.tokens or 0),
                    "cost": float(row.cost or 0)
                }
            
            return {
                "period_days": days,
                "daily_usage": daily_usage,
                "team_id": str(team_id)
            }
