"""Unit tests for URL validator."""
import pytest
from app.services.url_validator import validate_url
from app.core.errors import InvalidURLError, InternalIPError


class TestURLValidator:
    """Test URL validation logic."""
    
    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        validate_url("http://example.com")
        # Should not raise
    
    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        validate_url("https://example.com")
        # Should not raise
    
    def test_valid_url_with_path(self):
        """Test valid URL with path."""
        validate_url("https://example.com/path/to/page")
        # Should not raise
    
    def test_empty_url(self):
        """Test empty URL raises error."""
        with pytest.raises(InvalidURLError, match="cannot be empty"):
            validate_url("")
    
    def test_none_url(self):
        """Test None URL raises error."""
        with pytest.raises(InvalidURLError):
            validate_url(None)
    
    def test_url_too_long(self):
        """Test URL exceeding max length."""
        long_url = "https://example.com/" + "a" * 2000
        with pytest.raises(InvalidURLError, match="too long"):
            validate_url(long_url)
    
    def test_invalid_scheme(self):
        """Test URL with invalid scheme."""
        with pytest.raises(InvalidURLError, match="must start with http"):
            validate_url("ftp://example.com")
    
    def test_no_scheme(self):
        """Test URL without scheme."""
        with pytest.raises(InvalidURLError):
            validate_url("example.com")
    
    def test_internal_ip_localhost(self):
        """Test localhost IP raises error."""
        with pytest.raises(InternalIPError):
            validate_url("http://127.0.0.1")
    
    def test_internal_ip_private(self):
        """Test private IP raises error."""
        with pytest.raises(InternalIPError):
            validate_url("http://192.168.1.1")
    
    def test_internal_ip_10_range(self):
        """Test 10.x.x.x IP raises error."""
        with pytest.raises(InternalIPError):
            validate_url("http://10.0.0.1")
    
    def test_internal_ip_172_range(self):
        """Test 172.16-31.x.x IP raises error."""
        with pytest.raises(InternalIPError):
            validate_url("http://172.16.0.1")
    
    def test_valid_public_ip(self):
        """Test valid public IP passes."""
        validate_url("http://8.8.8.8")
        # Should not raise
