"""
Vector embedding and similarity search service
"""

import os
from typing import List, Optional
from uuid import UUID
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    class SentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass
        def encode(self, text: str):
            # Return zero embeddings of default dimension
            return [0.0] * 384
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.sql import func

from models.database import Comment
from utils.database import get_session


class VectorService:
    """Service for generating embeddings and performing similarity search"""
    
    def __init__(self):
        # Initialize sentence transformer model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_dim = 384  # all-MiniLM-L6-v2 produces 384-dim embeddings
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        if not text or not text.strip():
            return [0.0] * self.embedding_dim
        
        try:
            # Generate embedding
            embedding = self.model.encode(text.strip())
            return embedding.tolist()
        except Exception as e:
            raise Exception(f"Embedding generation failed: {str(e)}")
    
    async def find_similar_comments(
        self,
        query_embedding: List[float],
        team_id: UUID,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Comment]:
        """Find similar comments using cosine similarity"""
        
        async with get_session() as db:
            try:
                # Use pgvector's cosine similarity operator
                stmt = text("""
                    SELECT c.*, 
                           (c.embedding <=> :query_embedding) as distance
                    FROM comments c
                    WHERE c.team_id = :team_id 
                      AND c.embedding IS NOT NULL
                      AND (c.embedding <=> :query_embedding) < :distance_threshold
                    ORDER BY c.embedding <=> :query_embedding
                    LIMIT :limit
                """)
                
                # Convert similarity threshold to distance threshold
                # cosine distance = 1 - cosine similarity
                distance_threshold = 1 - similarity_threshold
                
                result = await db.execute(
                    stmt,
                    {
                        "query_embedding": query_embedding,
                        "team_id": str(team_id),
                        "distance_threshold": distance_threshold,
                        "limit": limit
                    }
                )
                
                rows = result.fetchall()
                
                # Convert rows to Comment objects
                comments = []
                for row in rows:
                    comment = Comment(
                        comment_id=row.comment_id,
                        team_id=row.team_id,
                        platform=row.platform,
                        author=row.author,
                        message=row.message,
                        post_id=row.post_id,
                        archived=row.archived,
                        flagged=row.flagged,
                        embedding=row.embedding,
                        metadata=row.metadata,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                    comments.append(comment)
                
                return comments
                
            except Exception as e:
                raise Exception(f"Similarity search failed: {str(e)}")
    
    async def update_comment_embedding(
        self,
        comment_id: UUID,
        embedding: List[float]
    ) -> bool:
        """Update comment with generated embedding"""
        
        async with get_session() as db:
            try:
                stmt = text("""
                    UPDATE comments 
                    SET embedding = :embedding, updated_at = NOW()
                    WHERE comment_id = :comment_id
                """)
                
                await db.execute(
                    stmt,
                    {
                        "embedding": embedding,
                        "comment_id": str(comment_id)
                    }
                )
                await db.commit()
                return True
                
            except Exception as e:
                raise Exception(f"Failed to update embedding: {str(e)}")
