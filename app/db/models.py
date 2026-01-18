from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from app.db.session import Base


def generate_uuid():
    """Generate a UUID string."""
    return str(uuid.uuid4())


class Device(Base):
    """Device model for tracking device registrations and quotas."""
    
    __tablename__ = "devices"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    device_fingerprint = Column(String, unique=True, nullable=False, index=True)
    quota_remaining = Column(Integer, nullable=False, default=3)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    device_model = Column(String, nullable=False)
    os_version = Column(String, nullable=False)
    
    # Relationship to tokens
    tokens = relationship("DeviceToken", back_populates="device", cascade="all, delete-orphan")
    # Ingestions relationship is defined via backref in Ingestion model


class DeviceToken(Base):
    """Device token model for authentication."""
    
    __tablename__ = "device_tokens"
    
    token_hash = Column(String, primary_key=True, unique=True, nullable=False, index=True)
    device_id = Column(String, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    
    # Relationship to device
    device = relationship("Device", back_populates="tokens")
    
    @property
    def is_active(self) -> bool:
        """Check if token is active (not revoked and not expired)."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at < datetime.utcnow():
            return False
        return True


class IngestionStatus(str, enum.Enum):
    """Ingestion status enum."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class QueryStatus(str, enum.Enum):
    """Query status enum."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Ingestion(Base):
    """Ingestion model for tracking URL scraping and processing."""
    
    __tablename__ = "ingestions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    device_id = Column(String, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(String, nullable=False, index=True)
    status = Column(SQLEnum(IngestionStatus), nullable=False, default=IngestionStatus.PENDING, index=True)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    estimated_time_seconds = Column(Integer, nullable=False, default=20)
    
    # Relationship to device
    device = relationship("Device", backref="ingestions")


class Query(Base):
    """Query model for tracking RAG queries and answers."""
    
    __tablename__ = "queries"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    device_id = Column(String, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    status = Column(SQLEnum(QueryStatus), nullable=False, default=QueryStatus.PENDING, index=True)
    chunk_count_used = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    estimated_time_seconds = Column(Integer, nullable=False, default=5)
    
    # Relationships
    device = relationship("Device", backref="queries")
    query_chunks = relationship("QueryChunk", back_populates="query", cascade="all, delete-orphan")


class QueryChunk(Base):
    """QueryChunk model for tracking which chunks were used in a query."""
    
    __tablename__ = "query_chunks"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    query_id = Column(String, ForeignKey("queries.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String, nullable=False)  # Reference to Chroma chunk ID
    ingestion_id = Column(String, ForeignKey("ingestions.id", ondelete="SET NULL"), nullable=True)
    relevance_score = Column(String, nullable=False)  # Store as string to preserve precision
    position = Column(Integer, nullable=False)  # Order in retrieval (0-based)
    text_snippet = Column(Text, nullable=False)  # First 200 chars for display
    
    # Relationships
    query = relationship("Query", back_populates="query_chunks")
    ingestion = relationship("Ingestion", backref="query_chunks")
