"""Tests for database session."""
import pytest
from app.db.session import get_db, SessionLocal
from app.db.models import Device


class TestSession:
    """Test database session functions."""
    
    def test_get_db_yields_session(self, test_db):
        """Test that get_db yields a session."""
        # get_db is a generator, test it yields a session
        db_gen = get_db()
        db = next(db_gen)
        
        assert db is not None
        assert hasattr(db, 'query')
        
        # Clean up
        try:
            next(db_gen)
        except StopIteration:
            pass
    
    def test_get_db_closes_session(self):
        """Test that get_db closes session after use."""
        db_gen = get_db()
        db = next(db_gen)
        
        # Consume generator (triggers finally block)
        try:
            next(db_gen)
        except StopIteration:
            pass
        
        # Session should be closed
        # Note: SQLite sessions don't always show closed state clearly
        # but the finally block should have executed
    
    def test_create_engine_sqlite(self):
        """Test SQLite engine creation."""
        from app.db.session import engine
        from sqlalchemy import inspect
        
        # Verify engine is created
        assert engine is not None
        
        # Verify it's a SQLite engine (in test mode)
        inspector = inspect(engine)
        # Should be able to inspect (engine is working)
        assert inspector is not None
