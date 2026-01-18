"""Unit tests for query service."""
import pytest
from app.services.query_service import validate_question, embed_query
from app.core.errors import InvalidQuestionError


class TestQueryService:
    """Test query service logic."""
    
    def test_validate_question_valid(self):
        """Test validation of valid question."""
        validate_question("What is machine learning?")
        # Should not raise
    
    def test_validate_question_too_short(self):
        """Test validation rejects too short question."""
        with pytest.raises(InvalidQuestionError, match="too short"):
            validate_question("short")
    
    def test_validate_question_too_long(self):
        """Test validation rejects too long question."""
        long_question = "a" * 600
        with pytest.raises(InvalidQuestionError, match="too long"):
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
