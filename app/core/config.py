from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "sqlite:///./rag_backend.db"
    device_fingerprint_salt: str = "change-me-in-production"
    environment: str = "development"
    
    # OpenAI - REQUIRED: Must be set via OPENAI_API_KEY environment variable
    openai_api_key: str  # No default - must be provided via environment
    
    # Chroma
    chroma_path: str = "./chroma_db"
    chroma_timeout_seconds: int = 10  # Timeout for Chroma operations
    
    # Scraping
    max_html_size_mb: int = 5
    max_tokens: int = 150000
    scraping_timeout: int = 10
    
    # Chunking
    chunk_size: int = 500
    chunk_overlap: float = 0.15
    min_chunk_size: int = 50  # Minimum tokens per chunk
    use_heading_aware_chunking: bool = True  # Enable heading-based chunking (future enhancement)
    
    # Query/RAG
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_timeout: int = 60  # Timeout for OpenAI embedding API calls
    max_query_length: int = 500
    min_query_length: int = 10
    default_max_chunks: int = 5
    max_max_chunks: int = 10
    max_context_tokens: int = 2000  # Reduced from 4000 for better token efficiency
    query_timeout_seconds: int = 30  # Timeout for OpenAI chat API calls
    
    # RAG Quality & Grounding
    min_similarity_threshold: float = 0.6  # Minimum cosine similarity (0-1) for chunk filtering
    snippet_max_chars: int = 150  # Maximum characters for source snippets (lower-relevance chunks)
    enable_strict_refusal: bool = True  # Enforce context-only answers with strict refusal mode
    similarity_filter_enabled: bool = True  # Filter chunks by similarity threshold
    
    # Background Task Timeouts
    ingestion_task_timeout_seconds: int = 300  # 5 minutes for ingestion tasks
    query_task_timeout_seconds: int = 120  # 2 minutes for query tasks
    
    # Background Task Queue
    background_task_queue_size: int = 50  # Maximum queue size for background tasks
    
    @field_validator('openai_api_key')
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        """Validate OpenAI API key is set and has correct format."""
        if not v or len(v.strip()) == 0:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required. "
                "Get your API key from https://platform.openai.com/api-keys"
            )
        if not v.startswith('sk-'):
            raise ValueError(
                "OPENAI_API_KEY appears to be invalid. "
                "OpenAI API keys should start with 'sk-'"
            )
        if len(v) < 20:
            raise ValueError("OPENAI_API_KEY appears to be too short (invalid format)")
        return v
    
    @field_validator('min_similarity_threshold')
    @classmethod
    def validate_similarity_threshold(cls, v: float) -> float:
        """Validate similarity threshold is in valid range (0.0 to 1.0)."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("min_similarity_threshold must be between 0.0 and 1.0")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # Allow .env file to be missing (will use environment variables only)
        env_ignore_empty = True


# Initialize settings
# Note: If .env file doesn't exist, pydantic-settings will use environment variables only
settings = Settings()
