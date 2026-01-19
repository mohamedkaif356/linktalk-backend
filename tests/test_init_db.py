"""Tests for database initialization."""
import pytest
from app.db.init_db import init_db
from app.db.session import engine, Base
from sqlalchemy import inspect


class TestInitDB:
    """Test database initialization."""
    
    def test_init_db_creates_tables(self, test_db):
        """Test that init_db creates all required tables."""
        # Verify tables exist
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected_tables = ['devices', 'device_tokens', 'ingestions', 'queries', 'query_chunks']
        for expected_table in expected_tables:
            assert expected_table in tables, f"Table {expected_table} not created!"
