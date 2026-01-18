"""OpenAI LLM service for generating answers."""
import openai
import logging
import time
import random
import threading
from typing import Optional, Tuple
from openai import OpenAI

from app.core.config import settings
from app.core.errors import QueryGenerationError

logger = logging.getLogger(__name__)

# Initialize OpenAI client
_client = None
_client_lock = threading.Lock()

# Circuit breaker state (thread-safe failure counter)
_circuit_breaker_failures = 0
_circuit_breaker_last_reset = time.time()
_circuit_breaker_open = False
_circuit_breaker_lock = threading.Lock()

# Strict system prompt for RAG with refusal mode
STRICT_SYSTEM_PROMPT = """You are a retrieval-augmented generation (RAG) assistant. Your ONLY job is to answer questions using EXCLUSIVELY the provided context.

CRITICAL RULES:
1. You MUST base your answer ONLY on the provided context. Do not use any external knowledge.
2. If the context does not contain enough information to answer the question, you MUST respond with: "I cannot answer this question based on the provided context. The context does not contain sufficient information."
3. If the context is irrelevant to the question, you MUST respond with: "I cannot answer this question based on the provided context. The context does not contain information relevant to this question."
4. Do NOT make up information. Do NOT infer beyond what is explicitly stated.
5. If you're uncertain, state that the context doesn't provide enough information.
6. Cite specific source numbers when referencing context (e.g., "According to Source 1...").

Your response must be grounded in the provided context. If you cannot answer from context alone, you MUST refuse to answer."""


def get_client() -> OpenAI:
    """Get or create OpenAI client (thread-safe singleton)."""
    global _client
    if _client is None:
        with _client_lock:
            # Double-check pattern for thread safety
            if _client is None:
                if not settings.openai_api_key:
                    raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")
                _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def _check_circuit_breaker() -> bool:
    """
    Check if circuit breaker is open (should fast-fail).
    Thread-safe implementation.
    
    Returns:
        True if circuit breaker is open (should fast-fail), False otherwise
    """
    global _circuit_breaker_failures, _circuit_breaker_last_reset, _circuit_breaker_open
    
    with _circuit_breaker_lock:
        current_time = time.time()
        
        # Reset counter after 5 minutes of success
        if current_time - _circuit_breaker_last_reset > 300:  # 5 minutes
            _circuit_breaker_failures = 0
            if _circuit_breaker_open:
                logger.info("Circuit breaker reset: failures cleared after 5 minutes")
                _circuit_breaker_open = False
        
        # Open circuit if >= 5 failures in last 5 minutes
        if _circuit_breaker_failures >= 5:
            if not _circuit_breaker_open:
                logger.warning("Circuit breaker opened: >= 5 failures in last 5 minutes")
                _circuit_breaker_open = True
            return True
        
        return False


def _record_circuit_breaker_success() -> None:
    """Record a successful API call (reset circuit breaker). Thread-safe."""
    global _circuit_breaker_failures, _circuit_breaker_last_reset, _circuit_breaker_open
    
    with _circuit_breaker_lock:
        if _circuit_breaker_failures > 0:
            _circuit_breaker_failures = 0
            _circuit_breaker_last_reset = time.time()
            if _circuit_breaker_open:
                logger.info("Circuit breaker closed: successful API call")
                _circuit_breaker_open = False


def _record_circuit_breaker_failure() -> None:
    """Record a failed API call (increment circuit breaker counter). Thread-safe."""
    global _circuit_breaker_failures
    with _circuit_breaker_lock:
        _circuit_breaker_failures += 1


def _calculate_backoff(attempt: int, error_type: str) -> float:
    """
    Calculate backoff delay based on attempt number and error type.
    
    Args:
        attempt: Attempt number (0-indexed)
        error_type: Type of error ("rate_limit", "server_error", "bad_gateway", "service_unavailable", "network_timeout", "api_timeout", "client_error")
        
    Returns:
        Backoff delay in seconds
    """
    if error_type == "rate_limit":
        return (2 ** attempt) + (random.random() * 1.0)  # Exponential + jitter
    elif error_type in ["server_error", "bad_gateway", "service_unavailable"]:
        return 2 ** attempt  # Exponential
    elif error_type == "network_timeout":
        return 5.0 * attempt  # Linear
    else:
        return 0.0  # No retry (client_error, api_timeout)


def generate_answer(
    question: str, 
    context: str, 
    temperature: float = 0.7, 
    max_retries: int = 3,
    strict_mode: bool = None
) -> Tuple[str, int]:
    """
    Generate an answer using OpenAI chat completions based on context.
    
    Implements error-type-specific retry strategy with circuit breaker.
    
    Args:
        question: User's question
        context: Retrieved context chunks
        temperature: Temperature for generation (0.0-2.0)
        max_retries: Maximum number of retry attempts (default: 3 for rate limits, 2 for server errors)
        strict_mode: Whether to use strict RAG mode with refusal (default: from config)
        
    Returns:
        Tuple of (generated answer text, token count)
        
    Raises:
        QueryGenerationError: If answer generation fails after retries
    """
    global _circuit_breaker_failures, _circuit_breaker_last_reset
    
    if not question or not context:
        raise ValueError("Question and context are required")
    
    # Check circuit breaker
    if _check_circuit_breaker():
        logger.warning("Circuit breaker is open, fast-failing request")
        raise QueryGenerationError(
            "CIRCUIT_BREAKER_OPEN",
            "OpenAI API is experiencing high failure rate. Please try again later."
        )
    
    # Use config default if strict_mode not specified
    if strict_mode is None:
        strict_mode = getattr(settings, 'enable_strict_refusal', True)
    
    client = get_client()
    
    # Choose system prompt based on mode
    system_content = STRICT_SYSTEM_PROMPT if strict_mode else "You are a helpful assistant that answers questions based on provided context."
    
    # Build user prompt
    user_prompt = f"""Context from ingested documents:
{context}

Question: {question}

Answer (based ONLY on the context above):"""
    
    last_error_type = None
    max_attempts = max_retries
    
    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=1000,
                timeout=settings.query_timeout_seconds
            )
            
            answer = response.choices[0].message.content.strip()
            token_count = response.usage.total_tokens if response.usage else 0
            
            # Record success (reset circuit breaker)
            _record_circuit_breaker_success()
            
            logger.info(f"Generated answer: {len(answer)} chars, {token_count} tokens (strict_mode={strict_mode})")
            return answer, token_count
            
        except openai.RateLimitError as e:
            last_error_type = "rate_limit"
            max_attempts = 3  # Rate limits: retry 3 times
            if attempt < max_attempts - 1:
                wait_time = _calculate_backoff(attempt, last_error_type)
                logger.warning(f"Rate limit hit, retrying in {wait_time:.2f}s (attempt {attempt + 1}/{max_attempts})")
                time.sleep(wait_time)
            else:
                logger.error(f"Rate limit error after {max_attempts} attempts: {e}")
                _record_circuit_breaker_failure()
                raise QueryGenerationError("RATE_LIMIT_EXCEEDED", f"OpenAI API rate limit exceeded: {e}") from e
                
        except openai.APIError as e:
            # Determine error type based on status code
            status_code = getattr(e, 'status_code', None)
            if status_code == 502:
                last_error_type = "bad_gateway"
            elif status_code == 503:
                last_error_type = "service_unavailable"
            elif status_code in [500, 501, 504]:
                last_error_type = "server_error"
            elif status_code in [400, 401, 403]:
                last_error_type = "client_error"
                max_attempts = 1  # Client errors: no retry
            else:
                last_error_type = "server_error"  # Default to server error
            
            # Server errors: retry 2 times (reduced from 3)
            if last_error_type in ["server_error", "bad_gateway", "service_unavailable"]:
                max_attempts = 2
            
            if attempt < max_attempts - 1 and last_error_type != "client_error":
                wait_time = _calculate_backoff(attempt, last_error_type)
                logger.warning(f"API error ({last_error_type}), retrying in {wait_time:.2f}s (attempt {attempt + 1}/{max_attempts}): {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"API error after {max_attempts} attempts: {e}")
                _record_circuit_breaker_failure()
                error_code = "OPENAI_CLIENT_ERROR" if last_error_type == "client_error" else "OPENAI_API_ERROR"
                raise QueryGenerationError(
                    error_code,
                    f"OpenAI API error (status: {status_code}): {e}"
                ) from e
                
        except openai.APITimeoutError as e:
            last_error_type = "api_timeout"
            max_attempts = 1  # API timeout: no retry (request too large/slow)
            logger.error(f"API timeout: {e}")
            _record_circuit_breaker_failure()
            raise QueryGenerationError("OPENAI_TIMEOUT", f"OpenAI API request timed out: {e}") from e
            
        except Exception as e:
            # Check if it's a network timeout
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                last_error_type = "network_timeout"
                max_attempts = 2  # Network timeout: retry 2 times
                if attempt < max_attempts - 1:
                    wait_time = _calculate_backoff(attempt, last_error_type)
                    logger.warning(f"Network timeout, retrying in {wait_time:.2f}s (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Network timeout after {max_attempts} attempts: {e}")
                    _record_circuit_breaker_failure()
                    raise QueryGenerationError("OPENAI_TIMEOUT", f"OpenAI API request timed out: {e}") from e
            else:
                logger.error(f"Unexpected error generating answer: {e}")
                _record_circuit_breaker_failure()
                raise QueryGenerationError("UNKNOWN_LLM_ERROR", f"An unexpected error occurred during LLM generation: {e}") from e
    
    _record_circuit_breaker_failure()
    raise QueryGenerationError("LLM_GENERATION_FAILED", "Failed to generate answer after all retries")
