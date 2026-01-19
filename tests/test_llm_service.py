"""Tests for LLM service."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import time
import openai
from app.services.llm_service import (
    get_client, _check_circuit_breaker, _record_circuit_breaker_success,
    _record_circuit_breaker_failure, generate_answer
)


class TestLLMService:
    """Test LLM service functions."""
    
    def test_get_client(self):
        """Test client initialization."""
        with patch('app.services.llm_service.OpenAI') as mock_openai:
            mock_client_instance = MagicMock()
            mock_openai.return_value = mock_client_instance
            
            client = get_client()
            assert client is not None
            mock_openai.assert_called_once()
    
    def test_check_circuit_breaker_closed(self):
        """Test circuit breaker in closed state."""
        # Reset circuit breaker
        import app.services.llm_service as llm_module
        with patch.object(llm_module, '_circuit_breaker_failures', 0), \
             patch.object(llm_module, '_circuit_breaker_open', False):
            result = _check_circuit_breaker()
            assert result is False
    
    def test_record_circuit_breaker_success(self):
        """Test recording circuit breaker success."""
        import app.services.llm_service as llm_module
        with patch.object(llm_module, '_circuit_breaker_failures', 5), \
             patch.object(llm_module, '_circuit_breaker_open', True), \
             patch.object(llm_module, '_circuit_breaker_last_reset', time.time()):
            _record_circuit_breaker_success()
            # Should reset failures
            assert llm_module._circuit_breaker_failures == 0
    
    def test_record_circuit_breaker_failure(self):
        """Test recording circuit breaker failure."""
        import app.services.llm_service as llm_module
        initial_failures = llm_module._circuit_breaker_failures
        _record_circuit_breaker_failure()
        # Should increment failures
        assert llm_module._circuit_breaker_failures == initial_failures + 1
    
    def test_generate_answer_success(self):
        """Test successful answer generation."""
        with patch('app.services.llm_service.get_client') as mock_get_client, \
             patch('app.services.llm_service._check_circuit_breaker') as mock_check:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_check.return_value = False  # Circuit breaker closed
            
            mock_choice = MagicMock()
            mock_choice.message.content = "Test answer"
            mock_usage = MagicMock()
            mock_usage.total_tokens = 100
            
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = mock_usage
            
            mock_client.chat.completions.create.return_value = mock_response
            
            answer, token_count = generate_answer("Test question", "Test context")
            
            assert answer == "Test answer"
            assert token_count == 100
    
    def test_generate_answer_retry_on_rate_limit(self):
        """Test retry on rate limit error."""
        with patch('app.services.llm_service.get_client') as mock_get_client, \
             patch('app.services.llm_service._check_circuit_breaker') as mock_check, \
             patch('app.services.llm_service.time.sleep') as mock_sleep:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_check.return_value = False
            
            mock_choice = MagicMock()
            mock_choice.message.content = "Test answer"
            mock_usage = MagicMock()
            mock_usage.total_tokens = 100
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = mock_usage
            
            # First call fails, second succeeds
            mock_client.chat.completions.create.side_effect = [
                openai.RateLimitError("Rate limit", response=MagicMock(), body={}),
                mock_response
            ]
            
            answer, token_count = generate_answer("Test question", "Test context", max_retries=3)
            
            assert answer == "Test answer"
            assert mock_sleep.called  # Retry happened
    
    def test_generate_answer_circuit_breaker_open(self):
        """Test fast-fail when circuit breaker is open."""
        with patch('app.services.llm_service._check_circuit_breaker') as mock_check:
            mock_check.return_value = True  # Circuit breaker open
            
            with pytest.raises(Exception) as exc_info:
                generate_answer("Test question", "Test context")
            assert "circuit breaker" in str(exc_info.value).lower()
