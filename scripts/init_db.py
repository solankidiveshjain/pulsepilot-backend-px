"""
Database initialization script for production deployment
"""

import asyncio
import os
import sys

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_init import init_supabase_database, create_indexes
from utils.logging import setup_logging, get_logger


async def main():
    """Main initialization function"""
    setup_logging()
    logger = get_logger(__name__)
    
    try:
        logger.info("Starting database initialization...")
        
        # Initialize database
        await init_supabase_database()
        
        # Create indexes
        await create_indexes()
        
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
