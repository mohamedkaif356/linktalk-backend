"""Tests for scraper service."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx
from app.services.scraper import (
    fetch_html, extract_readable_content, truncate_text, 
    estimate_tokens, _get_browser_headers
)
from app.core.errors import ScrapingError


class TestScraper:
    """Test scraper functions."""
    
    def test_fetch_html_success(self):
        """Test successful HTML fetch."""
        with patch('app.services.scraper.httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Test content</body></html>"
            mock_response.headers = {'content-length': '100'}
            mock_client.get.return_value = mock_response
            
            result = fetch_html("https://example.com")
            assert result == "<html><body>Test content</body></html>"
            mock_client.get.assert_called_once()
    
    def test_fetch_html_timeout(self):
        """Test fetch with timeout."""
        with patch('app.services.scraper.httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_client.get.side_effect = httpx.TimeoutException("Request timed out")
            
            with pytest.raises(ScrapingError) as exc_info:
                fetch_html("https://example.com")
            assert exc_info.value.error_code == "NETWORK_TIMEOUT"
    
    def test_fetch_html_http_error(self):
        """Test fetch with HTTP error."""
        with patch('app.services.scraper.httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.reason_phrase = "Not Found"
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404 Not Found", request=MagicMock(), response=mock_response
            )
            mock_client.get.return_value = mock_response
            
            with pytest.raises(ScrapingError) as exc_info:
                fetch_html("https://example.com")
            assert exc_info.value.error_code == "HTTP_ERROR"
    
    def test_fetch_html_rate_limit(self):
        """Test fetch with rate limit error."""
        with patch('app.services.scraper.httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.reason_phrase = "Too Many Requests"
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "429 Too Many Requests", request=MagicMock(), response=mock_response
            )
            mock_client.get.return_value = mock_response
            
            with pytest.raises(ScrapingError) as exc_info:
                fetch_html("https://example.com")
            assert exc_info.value.error_code == "HTTP_ERROR"
            assert "Too many requests" in exc_info.value.message
    
    def test_fetch_html_network_error(self):
        """Test fetch with network error."""
        with patch('app.services.scraper.httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_client.get.side_effect = httpx.RequestError("Network error")
            
            with pytest.raises(ScrapingError) as exc_info:
                fetch_html("https://example.com")
            assert exc_info.value.error_code == "NETWORK_ERROR"
    
    def test_extract_readable_content_beautifulsoup(self):
        """Test content extraction with BeautifulSoup."""
        html = "<html><body><main><p>Test content here</p></main></body></html>"
        with patch('app.services.scraper._extract_with_beautifulsoup') as mock_bs:
            mock_bs.return_value = "Test content here"
            result = extract_readable_content(html)
            assert result == "Test content here"
            mock_bs.assert_called_once_with(html)
    
    def test_extract_readable_content_readability(self):
        """Test content extraction with readability."""
        html = "<html><body><article><p>Test content</p></article></body></html>"
        with patch('app.services.scraper._extract_with_beautifulsoup') as mock_bs, \
             patch('app.services.scraper.Document') as mock_doc:
            mock_bs.return_value = ""  # BeautifulSoup fails
            mock_doc_instance = MagicMock()
            mock_doc_instance.summary.return_value = "<p>Test content</p>"
            mock_doc.return_value = mock_doc_instance
            
            result = extract_readable_content(html)
            assert "Test content" in result
    
    def test_extract_readable_content_fallback(self):
        """Test content extraction fallback."""
        html = "<html><body><p>Test content</p></body></html>"
        with patch('app.services.scraper._extract_with_beautifulsoup') as mock_bs, \
             patch('app.services.scraper.Document') as mock_doc, \
             patch('app.services.scraper._fallback_extract') as mock_fallback:
            mock_bs.return_value = ""  # BeautifulSoup fails
            mock_doc_instance = MagicMock()
            mock_doc_instance.summary.return_value = ""  # Readability fails
            mock_doc.return_value = mock_doc_instance
            mock_fallback.return_value = "Test content"
            
            result = extract_readable_content(html)
            assert result == "Test content"
            mock_fallback.assert_called_once_with(html)
    
    def test_truncate_text(self):
        """Test text truncation."""
        from app.services.scraper import truncate_text
        
        # Create long text
        long_text = "Word " * 1000  # ~5000 words
        
        # Truncate to 100 tokens (roughly 100 words)
        truncated = truncate_text(long_text, max_tokens=100)
        
        # Should be shorter
        assert len(truncated) < len(long_text)
        assert "Word" in truncated
    
    def test_estimate_tokens(self):
        """Test token estimation."""
        from app.services.scraper import estimate_tokens
        
        text = "This is a test sentence."
        token_count = estimate_tokens(text)
        
        assert token_count > 0
        assert isinstance(token_count, int)
    
    def test_get_browser_headers(self):
        """Test browser headers generation."""
        headers = _get_browser_headers()
        
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Mozilla" in headers["User-Agent"]
