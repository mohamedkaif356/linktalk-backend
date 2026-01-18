"""Initialize database tables."""
import logging
from app.db.session import engine, Base
from app.db.models import Device, DeviceToken, Ingestion, Query, QueryChunk

logger = logging.getLogger(__name__)


def init_db():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


if __name__ == "__main__":
    # Setup basic logging for CLI usage
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    init_db()
    logger.info("Database initialization complete")
