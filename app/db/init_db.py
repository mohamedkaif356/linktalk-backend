"""Initialize database tables."""
import logging
import os
from pathlib import Path
from app.db.session import engine, Base
from app.db.models import Device, DeviceToken, Ingestion, Query, QueryChunk
from app.core.config import settings

logger = logging.getLogger(__name__)


def init_db():
    """Create all database tables."""
    # Ensure database directory exists for SQLite
    if settings.database_url.startswith("sqlite"):
        # Extract file path from SQLite URL (e.g., "sqlite:///./rag_backend.db" -> "./rag_backend.db")
        db_path = settings.database_url.replace("sqlite:///", "")
        if db_path and db_path != ":memory:":
            # Get absolute path and ensure directory exists
            db_file = Path(db_path).resolve()
            db_file.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Database file path: {db_file}")
    
    # Import all models to ensure they're registered with Base.metadata
    # This is already done above, but explicit for clarity
    _ = Device, DeviceToken, Ingestion, Query, QueryChunk
    
    # Create all tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected_tables = ['devices', 'device_tokens', 'ingestions', 'queries', 'query_chunks']
        created_tables = [t for t in expected_tables if t in tables]
        missing_tables = [t for t in expected_tables if t not in tables]
        
        if missing_tables:
            logger.warning(f"Some tables were not created: {missing_tables}")
        else:
            logger.info(f"All expected tables created: {created_tables}")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}", exc_info=True)
        raise  # Re-raise to ensure startup fails if DB init fails


if __name__ == "__main__":
    # Setup basic logging for CLI usage
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    init_db()
    logger.info("Database initialization complete")
