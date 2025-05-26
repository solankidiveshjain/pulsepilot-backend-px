#!/usr/bin/env python3
"""
Database migration script for PulsePilot backend.
Supports forward migrations, rollbacks, and dry-run mode.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional

from utils.database import get_database
from utils.logging import setup_logging

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database migrations with safety checks and rollback support."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.migration_dir = Path("migrations/sql")
        
    async def get_applied_migrations(self) -> List[str]:
        """Get list of already applied migrations."""
        try:
            query = """
            SELECT migration_name FROM schema_migrations 
            ORDER BY applied_at ASC
            """
            result = await self.db.fetch(query)
            return [row['migration_name'] for row in result]
        except Exception:
            # Migration table doesn't exist yet
            await self.create_migration_table()
            return []
    
    async def create_migration_table(self):
        """Create the schema_migrations table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id SERIAL PRIMARY KEY,
            migration_name VARCHAR(255) UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        await self.db.execute(query)
        logger.info("Created schema_migrations table")
    
    async def get_pending_migrations(self) -> List[Path]:
        """Get list of pending migration files."""
        if not self.migration_dir.exists():
            logger.warning(f"Migration directory {self.migration_dir} does not exist")
            return []
        
        applied = await self.get_applied_migrations()
        all_migrations = sorted(self.migration_dir.glob("*.sql"))
        
        pending = []
        for migration_file in all_migrations:
            if migration_file.stem not in applied:
                pending.append(migration_file)
        
        return pending
    
    async def apply_migration(self, migration_file: Path, dry_run: bool = False) -> bool:
        """Apply a single migration file."""
        try:
            with open(migration_file, 'r') as f:
                sql_content = f.read()
            
            if dry_run:
                logger.info(f"DRY RUN: Would apply migration {migration_file.name}")
                logger.info(f"SQL Content:\n{sql_content}")
                return True
            
            # Execute migration in transaction
            async with self.db.transaction():
                await self.db.execute(sql_content)
                
                # Record migration as applied
                await self.db.execute(
                    "INSERT INTO schema_migrations (migration_name) VALUES ($1)",
                    migration_file.stem
                )
            
            logger.info(f"✅ Applied migration: {migration_file.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to apply migration {migration_file.name}: {e}")
            return False
    
    async def rollback_migration(self, migration_name: str, dry_run: bool = False) -> bool:
        """Rollback a specific migration (if rollback script exists)."""
        rollback_file = self.migration_dir / f"{migration_name}_rollback.sql"
        
        if not rollback_file.exists():
            logger.error(f"No rollback script found for {migration_name}")
            return False
        
        try:
            with open(rollback_file, 'r') as f:
                sql_content = f.read()
            
            if dry_run:
                logger.info(f"DRY RUN: Would rollback migration {migration_name}")
                logger.info(f"Rollback SQL:\n{sql_content}")
                return True
            
            # Execute rollback in transaction
            async with self.db.transaction():
                await self.db.execute(sql_content)
                
                # Remove migration record
                await self.db.execute(
                    "DELETE FROM schema_migrations WHERE migration_name = $1",
                    migration_name
                )
            
            logger.info(f"✅ Rolled back migration: {migration_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to rollback migration {migration_name}: {e}")
            return False
    
    async def run_forward_migrations(self, dry_run: bool = False) -> bool:
        """Run all pending forward migrations."""
        pending = await self.get_pending_migrations()
        
        if not pending:
            logger.info("No pending migrations to apply")
            return True
        
        logger.info(f"Found {len(pending)} pending migrations")
        
        success_count = 0
        for migration_file in pending:
            if await self.apply_migration(migration_file, dry_run):
                success_count += 1
            else:
                logger.error(f"Migration failed, stopping at {migration_file.name}")
                break
        
        if success_count == len(pending):
            logger.info(f"✅ All {success_count} migrations completed successfully")
            return True
        else:
            logger.error(f"❌ Only {success_count}/{len(pending)} migrations completed")
            return False


async def main():
    """Main migration script entry point."""
    parser = argparse.ArgumentParser(description="Database migration tool")
    parser.add_argument(
        "--type", 
        choices=["forward", "rollback"], 
        default="forward",
        help="Migration type"
    )
    parser.add_argument(
        "--migration", 
        help="Specific migration name for rollback"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Preview changes without applying them"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)
    
    try:
        # Get database connection
        db = get_database()
        migration_manager = MigrationManager(db)
        
        if args.type == "forward":
            success = await migration_manager.run_forward_migrations(args.dry_run)
        elif args.type == "rollback":
            if not args.migration:
                logger.error("--migration required for rollback")
                sys.exit(1)
            success = await migration_manager.rollback_migration(args.migration, args.dry_run)
        
        if success:
            logger.info("Migration completed successfully")
            sys.exit(0)
        else:
            logger.error("Migration failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Migration script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
