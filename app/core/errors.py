from fastapi import HTTPException, status
from typing import Optional, Dict, Any


class APIError(HTTPException):
    """Base API error with consistent error code format."""
    
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "code": code,
                "message": message,
                "details": details or {}
            }
        )


class MissingFieldError(APIError):
    """400 error for missing required fields."""
    
    def __init__(self, field_name: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MISSING_FIELD",
            message=f"Missing required field: {field_name}",
            details={"field": field_name}
        )


class InvalidDeviceInfoError(APIError):
    """400 error for invalid device information."""
    
    def __init__(self, reason: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_DEVICE_INFO",
            message=f"Invalid device information: {reason}",
            details={"reason": reason}
        )


class UnauthorizedError(APIError):
    """401 error for invalid or missing device token."""
    
    def __init__(self, reason: str = "Invalid or missing device token"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message=reason,
            details={}
        )


class InvalidURLError(APIError):
    """400 error for invalid URL format."""
    
    def __init__(self, reason: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_URL",
            message=f"Invalid URL: {reason}",
            details={"reason": reason}
        )


class InternalIPError(APIError):
    """400 error for internal/reserved IP addresses."""
    
    def __init__(self, ip: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INTERNAL_IP_NOT_ALLOWED",
            message=f"Internal or reserved IP addresses are not allowed: {ip}",
            details={"ip": ip}
        )


class URLAlreadyIngestedError(APIError):
    """400 error when device tries to ingest a second URL."""
    
    def __init__(self, existing_url: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="URL_ALREADY_INGESTED",
            message="Device has already ingested a URL. Only one URL per device is allowed.",
            details={"existing_url": existing_url}
        )


class ForbiddenError(APIError):
    """403 error for forbidden access."""
    
    def __init__(self, reason: str = "Access forbidden"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=reason,
            details={}
        )


class ScrapingError(Exception):
    """Internal exception for scraping errors (not HTTP)."""
    
    def __init__(self, error_code: str, message: str = ""):
        self.error_code = error_code
        self.message = message
        super().__init__(f"{error_code}: {message}")


class InvalidQuestionError(APIError):
    """400 error for invalid question format."""
    
    def __init__(self, reason: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_QUESTION",
            message=f"Invalid question: {reason}",
            details={"reason": reason}
        )


class NoContentError(APIError):
    """404 error when device has no ingested content."""
    
    def __init__(self, message: str = None):
        """
        Initialize NoContentError with optional custom message.
        
        Args:
            message: Optional custom error message. If None, uses default message.
        """
        msg = message or "No ingested content available for this device"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NO_CONTENT",
            message=msg,
            details={}
        )


class QuotaExhaustedError(APIError):
    """403 error when device quota is exhausted."""
    
    def __init__(self, quota_used: int = None, quota_total: int = None):
        """
        Initialize QuotaExhaustedError with optional quota details.
        
        Args:
            quota_used: Number of queries used (optional)
            quota_total: Total quota allowed (optional)
        """
        details = {}
        if quota_used is not None:
            details["quota_used"] = quota_used
        if quota_total is not None:
            details["quota_total"] = quota_total
        
        message = "Device quota exhausted. You have used all 3 queries. Register a new device for additional queries."
        if quota_used is not None and quota_total is not None:
            message = f"Device quota exhausted. You have used {quota_used}/{quota_total} queries. Register a new device for additional queries."
        
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="QUOTA_EXHAUSTED",
            message=message,
            details=details
        )


class QueryGenerationError(Exception):
    """Internal exception for query generation errors (not HTTP)."""
    
    def __init__(self, error_code: str, message: str = ""):
        self.error_code = error_code
        self.message = message
        super().__init__(f"{error_code}: {message}")
