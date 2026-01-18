"""Web scraping service."""
import httpx
import logging
from typing import Optional
from readability import Document
from bs4 import BeautifulSoup
import tiktoken

from app.core.config import settings
from app.core.errors import ScrapingError

logger = logging.getLogger(__name__)

# Initialize tiktoken encoder
_encoder = tiktoken.get_encoding("cl100k_base")


def _get_browser_headers() -> dict:
    """
    Get browser-like headers to avoid blocking by websites.
    
    Note: We don't include Accept-Encoding here because httpx handles
    decompression automatically, and explicitly requesting compression
    can sometimes cause issues with certain servers.
    
    Returns:
        Dictionary of HTTP headers that mimic a real browser
    """
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        # Don't explicitly request compression - httpx handles it automatically
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0"
    }


def fetch_html(url: str) -> str:
    """
    Fetch HTML content from URL with timeout and redirect handling.
    Uses browser-like headers to avoid blocking by websites.
    
    Args:
        url: URL to fetch
        
    Returns:
        HTML content as string
        
    Raises:
        ScrapingError: If fetching fails
    """
    try:
        headers = _get_browser_headers()
        
        with httpx.Client(
            timeout=settings.scraping_timeout,
            follow_redirects=True,
            max_redirects=5,
            headers=headers
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            
            # httpx automatically handles decompression (gzip, deflate, br) when accessing response.text
            # Use response.text instead of response.content to ensure proper decompression
            html_text = response.text
            
            # Check content size (after decompression)
            content_length = len(html_text.encode('utf-8'))
            max_size = settings.max_html_size_mb * 1024 * 1024
            
            if content_length > max_size:
                logger.warning(f"HTML size ({content_length} bytes) exceeds max ({max_size} bytes), truncating")
                # Truncate at character boundary
                truncated_chars = max_size // 4  # Rough estimate: 4 bytes per char
                html_text = html_text[:truncated_chars]
            
            return html_text
            
    except httpx.TimeoutException:
        raise ScrapingError("NETWORK_TIMEOUT", f"Request timed out after {settings.scraping_timeout} seconds")
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        reason = e.response.reason_phrase
        
        # Provide more helpful error messages for common status codes
        if status_code == 403:
            raise ScrapingError(
                "HTTP_ERROR", 
                f"HTTP {status_code}: {reason}. The website blocked the request. This may be due to anti-bot protection."
            )
        elif status_code == 404:
            raise ScrapingError("HTTP_ERROR", f"HTTP {status_code}: {reason}. The URL was not found.")
        elif status_code == 429:
            raise ScrapingError("HTTP_ERROR", f"HTTP {status_code}: {reason}. Too many requests. Please try again later.")
        else:
            raise ScrapingError("HTTP_ERROR", f"HTTP {status_code}: {reason}")
    except httpx.RequestError as e:
        raise ScrapingError("NETWORK_ERROR", f"Network error: {str(e)}")
    except Exception as e:
        raise ScrapingError("FETCH_ERROR", f"Unexpected error: {str(e)}")


def extract_readable_content(html: str) -> str:
    """
    Extract readable content from HTML using BeautifulSoup4 (primary) and readability-lxml (fallback).
    Optimized for product websites, blog posts, and general content pages.
    
    Args:
        html: HTML content
        
    Returns:
        Extracted text content
        
    Raises:
        ScrapingError: If extraction fails or returns empty content
    """
    # Strategy 1: Try BeautifulSoup4 for product/e-commerce sites
    try:
        text = _extract_with_beautifulsoup(html)
        if text and len(text) >= 10:
            logger.info("Successfully extracted content using BeautifulSoup4")
            return text
    except Exception as e:
        logger.debug(f"BeautifulSoup4 extraction attempt failed: {e}")
    
    # Strategy 2: Try readability-lxml (works well for articles/blog posts)
    try:
        doc = Document(html)
        content = doc.summary()
        
        from html import unescape
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', content)
        # Unescape HTML entities
        text = unescape(text)
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        if text and len(text) >= 10:
            logger.info("Successfully extracted content using readability-lxml")
            return text
    except Exception as e:
        logger.debug(f"Readability extraction attempt failed: {e}")
    
    # Strategy 3: Fallback to basic HTML parsing
    logger.warning("Primary extraction methods failed, using fallback")
    return _fallback_extract(html)


def _extract_with_beautifulsoup(html: str) -> str:
    """
    Extract content using BeautifulSoup4, optimized for product pages and e-commerce sites.
    
    Args:
        html: HTML content
        
    Returns:
        Extracted text content
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove script, style, and other non-content elements
    for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript']):
        element.decompose()
    
    # Priority order for content extraction (product pages, articles, etc.)
    content_parts = []
    
    # 1. Try to find main content containers (common in product pages)
    main_selectors = [
        'main', 'article', '[role="main"]',
        '.product-details', '.product-info', '.product-description',
        '.content', '.main-content', '.post-content',
        '#content', '#main-content', '#product-content'
    ]
    
    for selector in main_selectors:
        elements = soup.select(selector)
        if elements:
            for elem in elements:
                text = elem.get_text(separator=' ', strip=True)
                if text and len(text) > 50:  # Minimum meaningful content
                    content_parts.append(text)
            if content_parts:
                break
    
    # 2. If no main content found, extract from common content tags
    if not content_parts:
        # Product-specific selectors
        product_selectors = [
            'h1', 'h2', 'h3',  # Headings
            '[itemprop="name"]', '[itemprop="description"]',  # Schema.org
            '.product-title', '.product-name', '.product-description',
            '.price', '.product-price',  # Price info
            '.specifications', '.product-specs', '.features',  # Specs
            'p', 'li', 'dd'  # General content
        ]
        
        for selector in product_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(separator=' ', strip=True)
                # Filter out very short or likely navigation items
                if text and 20 <= len(text) <= 2000:  # Reasonable length
                    content_parts.append(text)
    
    # 3. If still no content, extract from all paragraphs and list items
    if not content_parts:
        for tag in ['p', 'li', 'dd', 'dt', 'td']:
            elements = soup.find_all(tag)
            for elem in elements:
                text = elem.get_text(separator=' ', strip=True)
                if text and len(text) > 20:
                    content_parts.append(text)
    
    # Combine all parts
    if not content_parts:
        # Last resort: get all text
        text = soup.get_text(separator=' ', strip=True)
    else:
        text = ' '.join(content_parts)
    
    # Clean up whitespace
    import re
    text = re.sub(r'\s+', ' ', text).strip()
    
    if not text or len(text) < 10:
        raise ScrapingError("NO_CONTENT", "No readable content extracted with BeautifulSoup4")
    
    return text


def _fallback_extract(html: str) -> str:
    """Fallback extraction using basic HTML parsing."""
    from html import unescape
    import re
    
    # Remove script and style tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Extract text from common content tags
    text_parts = re.findall(r'<[p|div|article|section|main|h1|h2|h3|h4|h5|h6][^>]*>(.*?)</[^>]+>', html, re.DOTALL | re.IGNORECASE)
    
    if not text_parts:
        # Last resort: extract all text
        text = re.sub(r'<[^>]+>', '', html)
    else:
        text = ' '.join(text_parts)
    
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    if not text or len(text) < 10:
        raise ScrapingError("NO_CONTENT", "No readable content found in HTML")
    
    return text


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using tiktoken.
    
    Args:
        text: Text to count tokens for
        
    Returns:
        Estimated token count
    """
    try:
        return len(_encoder.encode(text))
    except Exception:
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return len(text) // 4


def truncate_text(text: str, max_tokens: int) -> str:
    """
    Truncate text to fit within max_tokens limit.
    
    Args:
        text: Text to truncate
        max_tokens: Maximum token count
        
    Returns:
        Truncated text
    """
    tokens = estimate_tokens(text)
    
    if tokens <= max_tokens:
        return text
    
    # Binary search for truncation point
    low, high = 0, len(text)
    target_length = len(text)
    
    while low < high:
        mid = (low + high) // 2
        sample = text[:mid]
        sample_tokens = estimate_tokens(sample)
        
        if sample_tokens <= max_tokens:
            low = mid + 1
            target_length = mid
        else:
            high = mid
    
    # Truncate at word boundary if possible
    truncated = text[:target_length]
    last_space = truncated.rfind(' ')
    if last_space > target_length * 0.9:  # Only if we're not losing too much
        truncated = truncated[:last_space]
    
    logger.info(f"Truncated text from {tokens} tokens to {estimate_tokens(truncated)} tokens")
    return truncated
