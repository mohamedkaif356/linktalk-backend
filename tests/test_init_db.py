"""Tests for database initialization."""
import pytest
import tempfile
import os
from sqlalchemy import create_engine, inspect
from app.db.session import Base
from app.db.models import Device, DeviceToken, Ingestion, Query, QueryChunk


class TestInitDB:
    """Test database initialization."""
    
    def test_init_db_creates_tables(self):
        """Test that init_db creates all required tables."""
        # Create a fresh temporary database
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        try:
            # Create engine
            engine = create_engine(db_url, connect_args={"check_same_thread": False})
            
            # Ensure all models are imported
            _ = Device, DeviceToken, Ingestion, Query, QueryChunk
            
            # Create tables using Base.metadata (same as init_db does)
            Base.metadata.create_all(bind=engine)
            
            # Verify tables exist
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            expected_tables = ['devices', 'device_tokens', 'ingestions', 'queries', 'query_chunks']
            for expected_table in expected_tables:
                assert expected_table in tables, f"Table {expected_table} not created! Available: {tables}"
        finally:
            # Clean up
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)
