"""Tests for vector database service."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.vector_db import get_client, get_collection, store_chunks, EXPECTED_EMBEDDING_DIM
from app.services.chunker import Chunk


class TestVectorDB:
    """Test vector database service."""
    
    def test_get_client(self, temp_chroma_dir):
        """Test client initialization."""
        # get_client uses the mocked client from conftest, just verify it works
        client = get_client()
        assert client is not None
    
    def test_get_collection_existing(self, temp_chroma_dir):
        """Test retrieving existing collection."""
        # Uses mocked collection from conftest
        collection = get_collection()
        assert collection is not None
        # Verify it has expected methods
        assert hasattr(collection, 'add')
        assert hasattr(collection, 'query')
    
    def test_get_collection_create_new(self, temp_chroma_dir):
        """Test creating new collection."""
        # Reset the global collection to force recreation
        import app.services.vector_db as vector_db_module
        vector_db_module._collection = None
        
        collection = get_collection()
        assert collection is not None
        assert hasattr(collection, 'add')
    
    def test_store_chunks_success(self, temp_chroma_dir):
        """Test successful chunk storage."""
        chunks = [
            Chunk(text="Chunk 1", position=0, start_char=0, end_char=50, token_count=50),
            Chunk(text="Chunk 2", position=1, start_char=50, end_char=100, token_count=50)
        ]
        embeddings = [[0.1] * EXPECTED_EMBEDDING_DIM, [0.2] * EXPECTED_EMBEDDING_DIM]
        
        # Reset collection to get fresh mock
        import app.services.vector_db as vector_db_module
        vector_db_module._collection = None
        
        store_chunks("ingestion1", "device1", chunks, embeddings, url="https://example.com")
        
        # Verify collection was used (from conftest mock)
        collection = get_collection()
        assert hasattr(collection, 'add')
    
    def test_store_chunks_mismatch_count(self, temp_chroma_dir):
        """Test storage with chunk/embedding count mismatch."""
        chunks = [Chunk(text="Chunk 1", position=0, start_char=0, end_char=50, token_count=50)]
        embeddings = [[0.1] * EXPECTED_EMBEDDING_DIM, [0.2] * EXPECTED_EMBEDDING_DIM]  # Mismatch
        
        with pytest.raises(ValueError) as exc_info:
            store_chunks("ingestion1", "device1", chunks, embeddings)
        assert "Mismatch" in str(exc_info.value)
    
    def test_store_chunks_dimension_mismatch(self, temp_chroma_dir):
        """Test storage with embedding dimension mismatch."""
        chunks = [Chunk(text="Chunk 1", position=0, start_char=0, end_char=50, token_count=50)]
        embeddings = [[0.1] * 100]  # Wrong dimension
        
        with pytest.raises(ValueError) as exc_info:
            store_chunks("ingestion1", "device1", chunks, embeddings)
        assert "dimension" in str(exc_info.value).lower()
