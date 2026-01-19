"""Unit tests for query service."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.query_service import (
    validate_question, embed_query, search_relevant_chunks, assemble_context
)
from app.core.errors import InvalidQuestionError, NoContentError


class TestQueryService:
    """Test query service logic."""
    
    def test_validate_question_valid(self):
        """Test validation of valid question."""
        validate_question("What is machine learning?")
        # Should not raise
    
    def test_validate_question_too_short(self):
        """Test validation rejects too short question."""
        with pytest.raises(InvalidQuestionError, match="at least"):
            validate_question("short")
    
    def test_validate_question_too_long(self):
        """Test validation rejects too long question."""
        long_question = "a" * 600
        with pytest.raises(InvalidQuestionError, match="at most"):
            validate_question(long_question)
    
    def test_validate_question_empty(self):
        """Test validation rejects empty question."""
        with pytest.raises(InvalidQuestionError):
            validate_question("")
    
    def test_validate_question_min_length(self):
        """Test validation accepts question at minimum length."""
        question = "a" * 10
        validate_question(question)
        # Should not raise
    
    def test_embed_query(self):
        """Test query embedding generation."""
        question = "What is artificial intelligence?"
        embedding = embed_query(question)
        assert len(embedding) == 1536  # Expected dimension
        assert all(isinstance(x, float) for x in embedding)
    
    def test_embed_query_normalized(self):
        """Test that embeddings are normalized."""
        question = "Test question for normalization"
        embedding = embed_query(question)
        # Check that embedding is normalized (L2 norm ≈ 1)
        import math
        norm = math.sqrt(sum(x * x for x in embedding))
        assert abs(norm - 1.0) < 0.01  # Allow small floating point error
    
    def test_search_relevant_chunks_success(self, temp_chroma_dir):
        """Test successful chunk search."""
        query_embedding = [0.1] * 1536
        
        with patch('app.services.query_service.get_collection') as mock_get_collection:
            mock_collection = MagicMock()
            mock_get_collection.return_value = mock_collection
            
            # Mock query results
            mock_collection.query.return_value = {
                'ids': [['chunk1', 'chunk2']],
                'documents': [['Doc 1', 'Doc 2']],
                'metadatas': [[
                    {'ingestion_id': 'ing1', 'device_id': 'dev1', 'position': 0},
                    {'ingestion_id': 'ing1', 'device_id': 'dev1', 'position': 1}
                ]],
                'distances': [[0.1, 0.2]]  # Low distance = high similarity
            }
            
            chunks = search_relevant_chunks(query_embedding, 'dev1', 'ing1', max_chunks=5)
            
            assert len(chunks) == 2
            assert chunks[0]['chunk_id'] == 'chunk1'
            assert chunks[0]['similarity'] > 0  # Should have similarity score
    
    def test_search_relevant_chunks_no_results(self, temp_chroma_dir):
        """Test chunk search with no results."""
        query_embedding = [0.1] * 1536
        
        with patch('app.services.query_service.get_collection') as mock_get_collection:
            mock_collection = MagicMock()
            mock_get_collection.return_value = mock_collection
            
            # Mock empty results
            mock_collection.query.return_value = {
                'ids': [[]],
                'documents': [[]],
                'metadatas': [[]],
                'distances': [[]]
            }
            
            with pytest.raises(NoContentError):
                search_relevant_chunks(query_embedding, 'dev1', 'ing1', max_chunks=5)
    
    def test_search_relevant_chunks_similarity_threshold(self, temp_chroma_dir):
        """Test chunk search with similarity threshold filtering."""
        query_embedding = [0.1] * 1536
        
        with patch('app.services.query_service.get_collection') as mock_get_collection:
            mock_collection = MagicMock()
            mock_get_collection.return_value = mock_collection
            
            # Mock results with varying distances (low distance = high similarity)
            mock_collection.query.return_value = {
                'ids': [['chunk1', 'chunk2', 'chunk3']],
                'documents': [['Doc 1', 'Doc 2', 'Doc 3']],
                'metadatas': [[
                    {'ingestion_id': 'ing1', 'device_id': 'dev1'},
                    {'ingestion_id': 'ing1', 'device_id': 'dev1'},
                    {'ingestion_id': 'ing1', 'device_id': 'dev1'}
                ]],
                'distances': [[0.1, 0.5, 0.9]]  # Only first should pass 0.6 threshold
            }
            
            chunks = search_relevant_chunks(query_embedding, 'dev1', 'ing1', max_chunks=5, min_similarity=0.6)
            
            # Should filter by similarity threshold
            assert len(chunks) >= 1
            assert all(chunk['similarity'] >= 0.6 for chunk in chunks)
    
    def test_assemble_context_full_chunks(self):
        """Test context assembly with full chunks."""
        chunks = [
            {'document': 'Chunk 1 content', 'similarity': 0.9, 'ingestion_id': 'ing1'},
            {'document': 'Chunk 2 content', 'similarity': 0.8, 'ingestion_id': 'ing1'}
        ]
        
        context, token_count = assemble_context(chunks, max_tokens=1000)
        
        assert 'Chunk 1 content' in context
        assert 'Chunk 2 content' in context
        assert token_count > 0
    
    def test_assemble_context_token_limit(self):
        """Test context assembly respects token limit."""
        # Create chunks that would exceed token limit
        chunks = [
            {'document': 'A' * 1000, 'similarity': 0.9, 'ingestion_id': 'ing1'},
            {'document': 'B' * 1000, 'similarity': 0.8, 'ingestion_id': 'ing1'},
            {'document': 'C' * 1000, 'similarity': 0.7, 'ingestion_id': 'ing1'}
        ]
        
        context, token_count = assemble_context(chunks, max_tokens=50)  # Small limit
        
        # Should truncate to fit within limit
        assert token_count <= 50
        assert len(context) > 0