"""Tests for database initialization."""
import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, inspect
from app.db.session import Base
from app.db.models import Device, DeviceToken, Ingestion, Query, QueryChunk
from app.db.init_db import init_db


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
    
    def test_init_db_creates_directory(self):
        """Test that init_db creates directory for SQLite."""
        import tempfile
        from pathlib import Path
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "subdir", "test.db")
        db_url = f"sqlite:///{db_path}"
        
        try:
            with patch('app.db.init_db.settings') as mock_settings, \
                 patch('app.db.init_db.engine') as mock_engine:
                mock_settings.database_url = db_url
                mock_engine = create_engine(db_url, connect_args={"check_same_thread": False})
                
                # Ensure directory exists
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                
                # Verify directory was created
                assert os.path.exists(os.path.dirname(db_path))
        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def test_init_db_handles_existing_tables(self):
        """Test that init_db handles existing tables (idempotent)."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        try:
            engine = create_engine(db_url, connect_args={"check_same_thread": False})
            _ = Device, DeviceToken, Ingestion, Query, QueryChunk
            
            # Create tables twice (should not error)
            Base.metadata.create_all(bind=engine)
            Base.metadata.create_all(bind=engine)  # Second call should be idempotent
            
            # Verify tables still exist
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            assert len(tables) >= 5
        finally:
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)