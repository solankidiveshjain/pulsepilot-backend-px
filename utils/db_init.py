"""
Database initialization utilities for Supabase
"""

import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlmodel import SQLModel

from models.database import *
from utils.logging import get_logger


logger = get_logger(__name__)


async def init_supabase_database():
    """Initialize Supabase database with required extensions and tables"""
    
    # Use non-pooling URL for schema operations
    database_url = os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("POSTGRES_URL")
    if not database_url:
        raise ValueError("Database URL not found")
    
    # Convert to asyncpg URL
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(database_url, echo=True)
    
    try:
        async with engine.begin() as conn:
            # Enable required extensions
            logger.info("Enabling required PostgreSQL extensions...")
            
            # Enable pgvector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            
            # Enable uuid-ossp for UUID generation
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"))
            
            # Create all tables
            logger.info("Creating database tables...")
            await conn.run_sync(SQLModel.metadata.create_all)
            
            # Insert default pricing data
            logger.info("Inserting default pricing data...")
            await conn.execute(text("""
                INSERT INTO pricing (usage_type, price_per_token, effective_date)
                VALUES 
                    ('embedding', 0.0001, NOW()),
                    ('classification', 0.0002, NOW()),
                    ('generation', 0.002, NOW())
                ON CONFLICT (usage_type) DO NOTHING;
            """))
            
            logger.info("Database initialization completed successfully")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise
    finally:
        await engine.dispose()


async def create_indexes():
    """Create additional indexes for performance"""
    
    database_url = os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("POSTGRES_URL")
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(database_url)
    
    try:
        async with engine.begin() as conn:
            logger.info("Creating performance indexes...")
            
            # Vector similarity index
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_comments_embedding_cosine 
                ON comments USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """))
            
            # Additional performance indexes
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_comments_team_platform 
                ON comments(team_id, platform);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_comments_created_at 
                ON comments(created_at DESC);
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_social_connections_team_platform 
                ON social_connections(team_id, platform, status);
            """))
            
            logger.info("Indexes created successfully")
            
    except Exception as e:
        logger.error(f"Index creation failed: {str(e)}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_supabase_database())
    asyncio.run(create_indexes())
