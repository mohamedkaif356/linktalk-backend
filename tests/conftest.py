"""Pytest configuration and fixtures."""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient
from typing import Generator

# Set test environment variables BEFORE importing app modules
# This prevents pydantic-settings from trying to read .env file
os.environ["ENVIRONMENT"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test123456789012345678901234567890123456789012345678901234567890"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DEVICE_FINGERPRINT_SALT"] = "test-salt-for-testing-only"

# Ensure .env file is not read during tests
if "ENV_FILE" in os.environ:
    del os.environ["ENV_FILE"]

# Import models first to ensure they're registered with Base.metadata
from app.db.models import Device, DeviceToken, Ingestion, Query, QueryChunk
from app.db.session import Base, get_db
from app.main import app
from app.core.config import settings


@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """Create a test database session."""
    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    
    # Ensure all models are imported and registered with Base.metadata
    # The models are already imported at the top of the file, but we reference them here
    # to ensure they're registered with Base.metadata
    _ = Device, DeviceToken, Ingestion, Query, QueryChunk
    
    # Create all tables - this must happen before creating sessions
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Override get_db dependency - this ensures FastAPI uses our test database
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    # Set the dependency override BEFORE yielding
    # This ensures the override is active when the client is created
    app.dependency_overrides[get_db] = override_get_db
    
    # Create a session to verify tables exist
    db = TestingSessionLocal()
    try:
        # Verify tables were created by trying a simple query
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert len(tables) > 0, f"Tables not created! Expected tables, got: {tables}"
        yield db
    finally:
        db.close()
        # Clear dependency overrides after test
        app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(test_db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database tables created."""
    # test_db fixture already creates tables and overrides get_db
    # Just create the client - dependency override is already set
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_device(test_db: Session) -> Device:
    """Create a test device."""
    device = Device(
        device_fingerprint="test_fingerprint_hash",
        quota_remaining=3,
        device_model="Test Device",
        os_version="1.0"
    )
    test_db.add(device)
    test_db.commit()
    test_db.refresh(device)
    return device


@pytest.fixture
def test_device_token(test_db: Session, test_device: Device) -> tuple[str, DeviceToken]:
    """Create a test device token and return (token, token_obj)."""
    import hashlib
    from datetime import datetime
    
    device_token = "test_token_12345"
    token_hash = hashlib.sha256(device_token.encode()).hexdigest()
    
    token_obj = DeviceToken(
        token_hash=token_hash,
        device_id=test_device.id,
        created_at=datetime.utcnow()
    )
    test_db.add(token_obj)
    test_db.commit()
    test_db.refresh(token_obj)
    
    return device_token, token_obj


@pytest.fixture
def test_ingestion(test_db: Session, test_device: Device) -> Ingestion:
    """Create a test ingestion."""
    from datetime import datetime
    from app.db.models import IngestionStatus
    
    ingestion = Ingestion(
        device_id=test_device.id,
        url="https://example.com",
        status=IngestionStatus.SUCCESS,
        chunk_count=10,
        token_count=1000,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    test_db.add(ingestion)
    test_db.commit()
    test_db.refresh(ingestion)
    return ingestion


@pytest.fixture
def temp_chroma_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for ChromaDB."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture(autouse=True)
def mock_openai_client(monkeypatch):
    """Mock OpenAI client for all tests."""
    class MockOpenAIClient:
        def __init__(self, *args, **kwargs):
            pass
        
        class embeddings:
            @staticmethod
            def create(*args, **kwargs):
                class MockResponse:
                    class MockData:
                        def __init__(self):
                            self.embedding = [0.1] * 1536
                    data = [MockData()] * (kwargs.get('input', ['test']) if isinstance(kwargs.get('input'), list) else 1)
                return MockResponse()
        
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    class MockResponse:
                        class MockChoice:
                            class MockMessage:
                                content = "Test answer"
                            message = MockMessage()
                        choices = [MockChoice()]
                        class MockUsage:
                            total_tokens = 100
                        usage = MockUsage()
                    return MockResponse()
    
    monkeypatch.setattr("app.services.embeddings.OpenAI", MockOpenAIClient)
    monkeypatch.setattr("app.services.llm_service.OpenAI", MockOpenAIClient)


@pytest.fixture(autouse=True)
def mock_chroma_client(monkeypatch, temp_chroma_dir):
    """Mock ChromaDB client for all tests."""
    class MockChromaCollection:
        def __init__(self):
            self._data = []
            self._count = 0
        
        def count(self):
            return self._count
        
        def add(self, *args, **kwargs):
            self._count += len(kwargs.get('ids', []))
            self._data.append(kwargs)
        
        def get(self, *args, **kwargs):
            return {
                'ids': [],
                'documents': [],
                'metadatas': [],
                'embeddings': []
            }
        
        def query(self, *args, **kwargs):
            return {
                'ids': [['test_id']],
                'documents': [['test document']],
                'metadatas': [[{'ingestion_id': 'test', 'device_id': 'test', 'position': 0}]],
                'distances': [[0.1]]
            }
    
    class MockChromaClient:
        def __init__(self, *args, **kwargs):
            self._collection = MockChromaCollection()
        
        def get_collection(self, *args, **kwargs):
            return self._collection
        
        def create_collection(self, *args, **kwargs):
            return self._collection
    
    monkeypatch.setattr("app.services.vector_db.chromadb.PersistentClient", MockChromaClient)
