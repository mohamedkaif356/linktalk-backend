"""URL validation service."""
from urllib.parse import urlparse
import ipaddress
import re
from typing import Optional

from app.core.errors import InvalidURLError, InternalIPError


def validate_url(url: str) -> None:
    """
    Validate URL format, scheme, length, and check for internal IPs.
    
    Raises:
        InvalidURLError: If URL format is invalid
        InternalIPError: If URL points to internal/reserved IP
    """
    if not url or not isinstance(url, str):
        raise InvalidURLError("URL cannot be empty")
    
    # Check length
    if len(url) > 2000:
        raise InvalidURLError("URL too long (max 2000 characters)")
    
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise InvalidURLError(f"Invalid URL format: {str(e)}")
    
    # Check scheme
    if parsed.scheme not in ["http", "https"]:
        raise InvalidURLError("URL must start with http:// or https://")
    
    # Check for hostname/IP
    hostname = parsed.hostname
    if not hostname:
        raise InvalidURLError("URL must contain a hostname")
    
    # Check for internal/reserved IPs
    _check_internal_ip(hostname)


def _check_internal_ip(hostname: str) -> None:
    """
    Check if hostname resolves to internal/reserved IP.
    
    Raises:
        InternalIPError: If hostname is an internal IP
    """
    # Try to parse as IP address
    try:
        ip = ipaddress.ip_address(hostname)
        
        # Check for internal/reserved IPs
        if ip.is_loopback:
            raise InternalIPError(hostname)
        if ip.is_private:
            raise InternalIPError(hostname)
        if ip.is_link_local:
            raise InternalIPError(hostname)
        if ip.is_reserved:
            raise InternalIPError(hostname)
            
    except ValueError:
        # Not an IP address, check for localhost variants
        localhost_patterns = [
            r'^localhost$',
            r'^127\.',
            r'^192\.168\.',
            r'^10\.',
            r'^169\.254\.',
            r'^172\.(1[6-9]|2[0-9]|3[0-1])\.',  # 172.16.0.0/12
        ]
        
        for pattern in localhost_patterns:
            if re.match(pattern, hostname, re.IGNORECASE):
                raise InternalIPError(hostname)
        
        # Not an internal IP, continue
        pass
