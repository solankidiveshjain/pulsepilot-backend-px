"""
RAG (Retrieval-Augmented Generation) service for AI reply suggestions
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from models.database import Comment, Reply, Team
from services.vector_service import VectorService
from services.llm_service import LLMService
from utils.database import get_session
from utils.logging import get_logger

logger = get_logger(__name__)


class RAGService:
    """RAG service for context-aware reply generation"""
    
    def __init__(self):
        self.vector_service = VectorService()
        self.llm_service = LLMService()
    
    async def generate_contextual_suggestions(
        self,
        comment: Comment,
        team_id: UUID,
        limit_similar: int = 5
    ) -> Dict[str, Any]:
        """Generate reply suggestions using RAG approach"""
        
        # 1. Generate embedding for the comment if not exists
        if not comment.embedding:
            embedding = await self.vector_service.generate_embedding(comment.message or "")
            comment.embedding = embedding
        
        # 2. Find similar comments with successful replies
        similar_contexts = await self._find_similar_reply_contexts(
            comment.embedding, 
            team_id, 
            limit_similar
        )
        
        # 3. Get team persona and guidelines
        persona_guidelines = await self._get_team_persona(team_id)
        
        # 4. Generate suggestions using LLM with RAG context
        suggestions = await self.llm_service.generate_reply_suggestions_with_rag(
            comment=comment,
            similar_contexts=similar_contexts,
            persona_guidelines=persona_guidelines,
            team_id=team_id
        )
        
        return suggestions
    
    async def _find_similar_reply_contexts(
        self,
        query_embedding: List[float],
        team_id: UUID,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Find similar comments with their successful replies"""
        
        async with get_session() as db:
            # Find similar comments that have replies
            stmt = text("""
                SELECT 
                    c.comment_id,
                    c.message as comment_message,
                    c.platform,
                    c.author,
                    c.metadata,
                    r.message as reply_message,
                    r.created_at as reply_created_at,
                    u.user_name as replier_name,
                    (c.embedding <=> :query_embedding) as similarity_distance
                FROM comments c
                JOIN replies r ON c.comment_id = r.comment_id
                JOIN users u ON r.user_id = u.user_id
                WHERE c.team_id = :team_id 
                  AND c.embedding IS NOT NULL
                  AND (c.embedding <=> :query_embedding) < 0.3
                ORDER BY c.embedding <=> :query_embedding
                LIMIT :limit
            """)
            
            result = await db.execute(
                stmt,
                {
                    "query_embedding": query_embedding,
                    "team_id": str(team_id),
                    "limit": limit
                }
            )
            
            contexts = []
            for row in result.fetchall():
                contexts.append({
                    "comment_id": row.comment_id,
                    "comment_message": row.comment_message,
                    "platform": row.platform,
                    "author": row.author,
                    "reply_message": row.reply_message,
                    "replier_name": row.replier_name,
                    "similarity_score": 1 - row.similarity_distance,
                    "metadata": row.metadata
                })
            
            return contexts
    
    async def _get_team_persona(self, team_id: UUID) -> str:
        """Get team's brand persona and guidelines"""
        
        async with get_session() as db:
            # Get team metadata for persona
            stmt = select(Team).where(Team.team_id == team_id)
            result = await db.execute(stmt)
            team = result.scalar_one_or_none()
            
            if team and hasattr(team, 'metadata') and team.metadata:
                persona = team.metadata.get('persona', {})
                return f"""
Brand Voice: {persona.get('voice', 'Professional and friendly')}
Tone: {persona.get('tone', 'Helpful and engaging')}
Guidelines: {persona.get('guidelines', 'Be responsive, helpful, and maintain brand consistency')}
Do Not: {persona.get('avoid', 'Avoid controversial topics, be overly promotional')}
"""
            
            # Default persona
            return """
Brand Voice: Professional and friendly
Tone: Helpful and engaging  
Guidelines: Be responsive, helpful, and maintain brand consistency
Do Not: Avoid controversial topics, be overly promotional
"""
