from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.core.config import settings

# Create database engine with connection pooling
# For SQLite, pooling is limited but we configure it for future PostgreSQL migration
if settings.database_url.startswith("sqlite"):
    # SQLite-specific configuration
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},  # SQLite-specific
        echo=settings.environment == "development",
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,  # SQLite uses file-based locking, but pool helps with connection reuse
        max_overflow=10,
    )
else:
    # PostgreSQL or other database
    engine = create_engine(
        settings.database_url,
        echo=settings.environment == "development",
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_pre_ping=True,  # Verify connections before using
    )

# Create declarative base for models
Base = declarative_base()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.
    Yields a database session and closes it after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
