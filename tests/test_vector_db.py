"""Tests for vector database service."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.vector_db import get_client, get_collection, store_chunks, EXPECTED_EMBEDDING_DIM
from app.services.chunker import Chunk


class TestVectorDB:
    """Test vector database service."""
    
    def test_get_client(self, temp_chroma_dir):
        """Test client initialization."""
        with patch('app.services.vector_db.chromadb.PersistentClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            client = get_client()
            assert client is not None
            mock_client_class.assert_called_once()
    
    def test_get_collection_existing(self, temp_chroma_dir):
        """Test retrieving existing collection."""
        with patch('app.services.vector_db.get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            mock_collection = MagicMock()
            mock_collection.metadata = {"hnsw:space": "cosine"}
            mock_client.get_collection.return_value = mock_collection
            
            collection = get_collection()
            assert collection == mock_collection
            mock_client.get_collection.assert_called_once_with(name="rag_chunks")
    
    def test_get_collection_create_new(self, temp_chroma_dir):
        """Test creating new collection."""
        with patch('app.services.vector_db.get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            # First call raises (collection doesn't exist), second creates
            mock_collection = MagicMock()
            mock_collection.metadata = {"hnsw:space": "cosine"}
            mock_client.get_collection.side_effect = [Exception("Not found"), mock_collection]
            mock_client.create_collection.return_value = mock_collection
            
            collection = get_collection()
            assert collection == mock_collection
            mock_client.create_collection.assert_called_once()
    
    def test_store_chunks_success(self, temp_chroma_dir):
        """Test successful chunk storage."""
        chunks = [
            Chunk(text="Chunk 1", position=0, token_count=50),
            Chunk(text="Chunk 2", position=1, token_count=50)
        ]
        embeddings = [[0.1] * EXPECTED_EMBEDDING_DIM, [0.2] * EXPECTED_EMBEDDING_DIM]
        
        with patch('app.services.vector_db.get_collection') as mock_get_collection:
            mock_collection = MagicMock()
            mock_get_collection.return_value = mock_collection
            
            store_chunks("ingestion1", "device1", chunks, embeddings, url="https://example.com")
            
            # Verify add was called
            assert mock_collection.add.called
            call_kwargs = mock_collection.add.call_args[1]
            assert len(call_kwargs['ids']) == 2
            assert len(call_kwargs['documents']) == 2
            assert len(call_kwargs['embeddings']) == 2
    
    def test_store_chunks_mismatch_count(self, temp_chroma_dir):
        """Test storage with chunk/embedding count mismatch."""
        chunks = [Chunk(text="Chunk 1", position=0, token_count=50)]
        embeddings = [[0.1] * EXPECTED_EMBEDDING_DIM, [0.2] * EXPECTED_EMBEDDING_DIM]  # Mismatch
        
        with pytest.raises(ValueError) as exc_info:
            store_chunks("ingestion1", "device1", chunks, embeddings)
        assert "Mismatch" in str(exc_info.value)
    
    def test_store_chunks_dimension_mismatch(self, temp_chroma_dir):
        """Test storage with embedding dimension mismatch."""
        chunks = [Chunk(text="Chunk 1", position=0, token_count=50)]
        embeddings = [[0.1] * 100]  # Wrong dimension
        
        with pytest.raises(ValueError) as exc_info:
            store_chunks("ingestion1", "device1", chunks, embeddings)
        assert "dimension" in str(exc_info.value).lower()
