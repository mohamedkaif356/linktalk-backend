"""Tests for error classes."""
import pytest
from fastapi import status
from app.core.errors import (
    APIError,
    MissingFieldError,
    InvalidDeviceInfoError,
    UnauthorizedError,
    InvalidURLError,
    InternalIPError,
    URLAlreadyIngestedError,
    ForbiddenError,
    InvalidQuestionError,
    NoContentError,
    QuotaExhaustedError,
    ScrapingError,
    QueryGenerationError
)


class TestAPIError:
    """Test base APIError class."""
    
    def test_api_error_creation(self):
        """Test APIError creation with all parameters."""
        error = APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="TEST_ERROR",
            message="Test error message",
            details={"key": "value"}
        )
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.detail["code"] == "TEST_ERROR"
        assert error.detail["message"] == "Test error message"
        assert error.detail["details"] == {"key": "value"}
    
    def test_api_error_no_details(self):
        """Test APIError creation without details."""
        error = APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="TEST_ERROR",
            message="Test error message"
        )
        assert error.detail["details"] == {}


class TestMissingFieldError:
    """Test MissingFieldError."""
    
    def test_missing_field_error(self):
        """Test MissingFieldError creation."""
        error = MissingFieldError("field_name")
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.detail["code"] == "MISSING_FIELD"
        assert "field_name" in error.detail["message"]
        assert error.detail["details"]["field"] == "field_name"


class TestInvalidDeviceInfoError:
    """Test InvalidDeviceInfoError."""
    
    def test_invalid_device_info_error(self):
        """Test InvalidDeviceInfoError creation."""
        error = InvalidDeviceInfoError("device_model too long")
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.detail["code"] == "INVALID_DEVICE_INFO"
        assert "device_model too long" in error.detail["message"]
        assert error.detail["details"]["reason"] == "device_model too long"


class TestUnauthorizedError:
    """Test UnauthorizedError."""
    
    def test_unauthorized_error_default(self):
        """Test UnauthorizedError with default message."""
        error = UnauthorizedError()
        assert error.status_code == status.HTTP_401_UNAUTHORIZED
        assert error.detail["code"] == "UNAUTHORIZED"
    
    def test_unauthorized_error_custom(self):
        """Test UnauthorizedError with custom message."""
        error = UnauthorizedError("Custom unauthorized message")
        assert error.status_code == status.HTTP_401_UNAUTHORIZED
        assert error.detail["code"] == "UNAUTHORIZED"
        assert error.detail["message"] == "Custom unauthorized message"


class TestInvalidURLError:
    """Test InvalidURLError."""
    
    def test_invalid_url_error(self):
        """Test InvalidURLError creation."""
        error = InvalidURLError("Invalid URL format")
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.detail["code"] == "INVALID_URL"
        assert "Invalid URL format" in error.detail["message"]


class TestInternalIPError:
    """Test InternalIPError."""
    
    def test_internal_ip_error(self):
        """Test InternalIPError creation."""
        error = InternalIPError("127.0.0.1")
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.detail["code"] == "INTERNAL_IP_NOT_ALLOWED"
        assert "127.0.0.1" in error.detail["message"]


class TestURLAlreadyIngestedError:
    """Test URLAlreadyIngestedError."""
    
    def test_url_already_ingested_error(self):
        """Test URLAlreadyIngestedError creation."""
        error = URLAlreadyIngestedError("https://example.com")
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.detail["code"] == "URL_ALREADY_INGESTED"
        assert error.detail["details"]["existing_url"] == "https://example.com"


class TestForbiddenError:
    """Test ForbiddenError."""
    
    def test_forbidden_error_default(self):
        """Test ForbiddenError with default message."""
        error = ForbiddenError()
        assert error.status_code == status.HTTP_403_FORBIDDEN
        assert error.detail["code"] == "FORBIDDEN"
    
    def test_forbidden_error_custom(self):
        """Test ForbiddenError with custom message."""
        error = ForbiddenError("Custom forbidden message")
        assert error.status_code == status.HTTP_403_FORBIDDEN
        assert error.detail["code"] == "FORBIDDEN"
        assert error.detail["message"] == "Custom forbidden message"


class TestInvalidQuestionError:
    """Test InvalidQuestionError."""
    
    def test_invalid_question_error(self):
        """Test InvalidQuestionError creation."""
        error = InvalidQuestionError("Question too short")
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.detail["code"] == "INVALID_QUESTION"
        assert "Question too short" in error.detail["message"]


class TestNoContentError:
    """Test NoContentError."""
    
    def test_no_content_error_default(self):
        """Test NoContentError with default message."""
        error = NoContentError()
        assert error.status_code == status.HTTP_404_NOT_FOUND
        assert error.detail["code"] == "NO_CONTENT"
    
    def test_no_content_error_custom(self):
        """Test NoContentError with custom message."""
        error = NoContentError("Custom no content message")
        assert error.status_code == status.HTTP_404_NOT_FOUND
        assert error.detail["code"] == "NO_CONTENT"
        assert error.detail["message"] == "Custom no content message"


class TestQuotaExhaustedError:
    """Test QuotaExhaustedError."""
    
    def test_quota_exhausted_error_no_details(self):
        """Test QuotaExhaustedError without quota details."""
        error = QuotaExhaustedError()
        assert error.status_code == status.HTTP_403_FORBIDDEN
        assert error.detail["code"] == "QUOTA_EXHAUSTED"
        assert error.detail["details"] == {}
    
    def test_quota_exhausted_error_with_details(self):
        """Test QuotaExhaustedError with quota details."""
        error = QuotaExhaustedError(quota_used=3, quota_total=3)
        assert error.status_code == status.HTTP_403_FORBIDDEN
        assert error.detail["code"] == "QUOTA_EXHAUSTED"
        assert error.detail["details"]["quota_used"] == 3
        assert error.detail["details"]["quota_total"] == 3
        assert "3/3" in error.detail["message"]


class TestScrapingError:
    """Test ScrapingError (internal exception)."""
    
    def test_scraping_error(self):
        """Test ScrapingError creation."""
        error = ScrapingError("SCRAPING_FAILED", "Failed to fetch URL")
        assert error.error_code == "SCRAPING_FAILED"
        assert error.message == "Failed to fetch URL"
        assert str(error) == "SCRAPING_FAILED: Failed to fetch URL"


class TestQueryGenerationError:
    """Test QueryGenerationError (internal exception)."""
    
    def test_query_generation_error(self):
        """Test QueryGenerationError creation."""
        error = QueryGenerationError("GENERATION_FAILED", "Failed to generate answer")
        assert error.error_code == "GENERATION_FAILED"
        assert error.message == "Failed to generate answer"
        assert str(error) == "GENERATION_FAILED: Failed to generate answer"
