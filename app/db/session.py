from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.core.config import settings

# Create database engine with connection pooling
# SQLite doesn't support connection pooling parameters (max_overflow, pool_size)
# Only apply pooling for non-SQLite databases (e.g., PostgreSQL)
if settings.database_url.startswith("sqlite"):
    # SQLite-specific configuration (no pooling parameters)
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},  # SQLite-specific
        echo=settings.environment == "development",
    )
else:
    # PostgreSQL or other database with connection pooling
    engine = create_engine(
        settings.database_url,
        echo=settings.environment == "development",
        pool_size=10,  # Maintain a pool of 10 connections
        max_overflow=20,  # Allow up to 20 connections to overflow the pool
        pool_timeout=30,  # Wait 30 seconds for a connection from the pool
        pool_pre_ping=True,  # Test connections for liveness
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
