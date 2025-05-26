"""
Database migration manager using Alembic
"""

import os
import asyncio
from typing import Optional
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine

from utils.config import get_config
from utils.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)


class MigrationManager:
    """Database migration manager with Alembic integration"""
    
    def __init__(self):
        """Initialize migration manager with database configuration"""
        self.config = get_config()
        self.alembic_cfg = Config("alembic.ini")
        
        # Use non-pooling URL for migrations
        migration_url = self.config.postgres_url_non_pooling or self.config.postgres_url
        if migration_url.startswith("postgresql://"):
            migration_url = migration_url.replace("postgresql://", "postgresql+asyncpg://")
        
        self.alembic_cfg.set_main_option("sqlalchemy.url", migration_url)
    
    def run_migrations(self) -> None:
        """
        Run all pending database migrations
        
        Raises:
            Exception: If migration fails
        """
        try:
            logger.info("Starting database migrations")
            command.upgrade(self.alembic_cfg, "head")
            logger.info("Database migrations completed successfully")
        except Exception as e:
            logger.error("Database migration failed", error=str(e))
            raise
    
    def create_migration(self, message: str) -> None:
        """
        Create new migration file
        
        Args:
            message: Migration description
        """
        try:
            logger.info("Creating new migration", message=message)
            command.revision(self.alembic_cfg, message=message, autogenerate=True)
            logger.info("Migration file created successfully")
        except Exception as e:
            logger.error("Migration creation failed", error=str(e))
            raise
    
    def get_current_revision(self) -> Optional[str]:
        """
        Get current database revision
        
        Returns:
            Current revision ID or None
        """
        try:
            from alembic.runtime.migration import MigrationContext
            from alembic.script import ScriptDirectory
            
            engine = create_async_engine(self.alembic_cfg.get_main_option("sqlalchemy.url"))
            
            async def get_revision():
                async with engine.begin() as conn:
                    context = MigrationContext.configure(conn)
                    return context.get_current_revision()
            
            return asyncio.run(get_revision())
        except Exception as e:
            logger.error("Failed to get current revision", error=str(e))
            return None
    
    def validate_schema(self) -> bool:
        """
        Validate database schema matches migrations
        
        Returns:
            True if schema is valid
        """
        try:
            # Check if current revision matches head
            current = self.get_current_revision()
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            head = script_dir.get_current_head()
            
            if current != head:
                logger.warning("Database schema is not up to date",
                             current_revision=current,
                             head_revision=head)
                return False
            
            logger.info("Database schema is up to date", revision=current)
            return True
        except Exception as e:
            logger.error("Schema validation failed", error=str(e))
            return False


# Global migration manager
migration_manager = MigrationManager()


# CLI commands for operations
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python migration_manager.py [migrate|create|validate] [message]")
        sys.exit(1)
    
    command_name = sys.argv[1]
    
    if command_name == "migrate":
        migration_manager.run_migrations()
    elif command_name == "create":
        if len(sys.argv) < 3:
            print("Migration message required")
            sys.exit(1)
        migration_manager.create_migration(sys.argv[2])
    elif command_name == "validate":
        if migration_manager.validate_schema():
            print("✅ Schema is valid")
        else:
            print("❌ Schema validation failed")
            sys.exit(1)
    else:
        print(f"Unknown command: {command_name}")
        sys.exit(1)
