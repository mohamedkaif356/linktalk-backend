"""Tests for embeddings service."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from app.services.embeddings import (
    get_client, normalize_embedding, generate_embeddings, EXPECTED_EMBEDDING_DIM
)


class TestEmbeddings:
    """Test embeddings service."""
    
    def test_get_client(self):
        """Test client initialization."""
        with patch('app.services.embeddings.OpenAI') as mock_openai:
            mock_client_instance = MagicMock()
            mock_openai.return_value = mock_client_instance
            
            client = get_client()
            assert client is not None
            mock_openai.assert_called_once()
    
    def test_normalize_embedding_success(self):
        """Test successful embedding normalization."""
        embedding = [1.0, 2.0, 3.0] + [0.0] * (EXPECTED_EMBEDDING_DIM - 3)
        normalized = normalize_embedding(embedding)
        
        assert len(normalized) == EXPECTED_EMBEDDING_DIM
        # Check it's normalized (L2 norm should be ~1)
        norm = np.linalg.norm(normalized)
        assert abs(norm - 1.0) < 0.01
    
    def test_normalize_embedding_wrong_dimension(self):
        """Test normalization with wrong dimension."""
        embedding = [1.0, 2.0, 3.0]  # Wrong dimension
        
        with pytest.raises(ValueError) as exc_info:
            normalize_embedding(embedding)
        assert "dimension mismatch" in str(exc_info.value).lower()
    
    def test_normalize_embedding_zero_norm(self):
        """Test normalization with zero-norm embedding."""
        embedding = [0.0] * EXPECTED_EMBEDDING_DIM
        
        # Should return original (avoid division by zero)
        result = normalize_embedding(embedding)
        assert result == embedding
    
    def test_generate_embeddings_success(self):
        """Test successful embedding generation."""
        texts = ["Test text 1", "Test text 2"]
        
        with patch('app.services.embeddings.get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            mock_data1 = MagicMock()
            mock_data1.embedding = [0.1] * EXPECTED_EMBEDDING_DIM
            mock_data2 = MagicMock()
            mock_data2.embedding = [0.2] * EXPECTED_EMBEDDING_DIM
            
            mock_response = MagicMock()
            mock_response.data = [mock_data1, mock_data2]
            
            mock_client.embeddings.create.return_value = mock_response
            
            embeddings = generate_embeddings(texts)
            
            assert len(embeddings) == 2
            assert len(embeddings[0]) == EXPECTED_EMBEDDING_DIM
            assert len(embeddings[1]) == EXPECTED_EMBEDDING_DIM
    
    def test_generate_embeddings_empty_list(self):
        """Test embedding generation with empty list."""
        embeddings = generate_embeddings([])
        assert embeddings == []
    
    def test_generate_embeddings_without_normalize(self):
        """Test embedding generation without normalization."""
        texts = ["Test text"]
        
        with patch('app.services.embeddings.get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            mock_data = MagicMock()
            mock_data.embedding = [0.1] * EXPECTED_EMBEDDING_DIM
            mock_response = MagicMock()
            mock_response.data = [mock_data]
            mock_client.embeddings.create.return_value = mock_response
            
            embeddings = generate_embeddings(texts, normalize=False)
            
            assert len(embeddings) == 1
            # Should not be normalized (norm != 1)
            norm = np.linalg.norm(embeddings[0])
            assert abs(norm - 1.0) > 0.1  # Not normalized
    
    def test_generate_embeddings_retry_on_rate_limit(self):
        """Test retry on rate limit error."""
        import openai
        texts = ["Test text"]
        
        with patch('app.services.embeddings.get_client') as mock_get_client, \
             patch('app.services.embeddings.time.sleep') as mock_sleep:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            # First call fails with rate limit, second succeeds
            mock_data = MagicMock()
            mock_data.embedding = [0.1] * EXPECTED_EMBEDDING_DIM
            mock_response = MagicMock()
            mock_response.data = [mock_data]
            
            mock_client.embeddings.create.side_effect = [
                openai.RateLimitError("Rate limit", response=MagicMock(), body={}),
                mock_response
            ]
            
            embeddings = generate_embeddings(texts, max_retries=3)
            
            assert len(embeddings) == 1
            assert mock_sleep.called  # Retry happened
    
    def test_generate_embeddings_dimension_validation(self):
        """Test dimension validation."""
        texts = ["Test text"]
        
        with patch('app.services.embeddings.get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            
            # Wrong dimension
            mock_data = MagicMock()
            mock_data.embedding = [0.1] * 100  # Wrong dimension
            mock_response = MagicMock()
            mock_response.data = [mock_data]
            mock_client.embeddings.create.return_value = mock_response
            
            with pytest.raises(ValueError) as exc_info:
                generate_embeddings(texts)
            assert "dimension" in str(exc_info.value).lower()
