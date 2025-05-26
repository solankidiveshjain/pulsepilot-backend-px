"""
Database utilities and connection management
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from models.database import *


# Database configuration
DATABASE_URL = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("Database URL not found. Please set POSTGRES_URL environment variable.")

# For Supabase, we need to handle connection pooling properly
if "supabase" in DATABASE_URL:
    # Use the non-pooling URL for migrations and the pooling URL for app connections
    POSTGRES_URL_NON_POOLING = os.getenv("POSTGRES_URL_NON_POOLING")
    if POSTGRES_URL_NON_POOLING:
        # Use non-pooling URL for schema operations
        MIGRATION_URL = POSTGRES_URL_NON_POOLING.replace("postgresql://", "postgresql+asyncpg://")
    else:
        MIGRATION_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    
    # Use pooling URL for regular operations
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    MIGRATION_URL = DATABASE_URL

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("ENVIRONMENT") == "development",
    future=True
)

# Create session factory
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncSession:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db():
    """Dependency for FastAPI to get database session"""
    async for session in get_session():
        yield session
