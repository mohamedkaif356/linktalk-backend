"""OpenAI embeddings service."""
import openai
import logging
import time
from typing import List
from openai import OpenAI
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

# Expected embedding dimension for text-embedding-3-small
EXPECTED_EMBEDDING_DIM = 1536

# Initialize OpenAI client
_client = None


def get_client() -> OpenAI:
    """Get or create OpenAI client."""
    global _client
    if _client is None:
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def normalize_embedding(embedding: List[float]) -> List[float]:
    """
    Normalize embedding vector to unit length (L2 norm).
    
    Args:
        embedding: Embedding vector as list of floats
        
    Returns:
        Normalized embedding vector (unit length)
        
    Raises:
        ValueError: If embedding dimension doesn't match expected dimension
    """
    if len(embedding) != EXPECTED_EMBEDDING_DIM:
        raise ValueError(
            f"Embedding dimension mismatch: expected {EXPECTED_EMBEDDING_DIM}, got {len(embedding)}"
        )
    
    vec = np.array(embedding, dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm == 0:
        logger.warning("Zero-norm embedding detected, returning original")
        return embedding  # Avoid division by zero
    normalized = (vec / norm).tolist()
    return normalized


def generate_embeddings(texts: List[str], normalize: bool = True, max_retries: int = 3) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using OpenAI API.
    
    Args:
        texts: List of texts to embed
        normalize: Whether to normalize embeddings to unit length (default: True)
        max_retries: Maximum number of retry attempts
        
    Returns:
        List of embedding vectors (each is a list of floats, normalized if normalize=True)
        
    Raises:
        Exception: If embedding generation fails after retries
    """
    if not texts:
        return []
    
    client = get_client()
    
    for attempt in range(max_retries):
        try:
            # Enforce timeout from settings
            timeout = getattr(settings, 'openai_embedding_timeout', 60)
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
                timeout=timeout
            )
            
            embeddings = [item.embedding for item in response.data]
            
            # Validate embedding dimensions
            for i, emb in enumerate(embeddings):
                if len(emb) != EXPECTED_EMBEDDING_DIM:
                    raise ValueError(
                        f"Embedding {i} has wrong dimension: {len(emb)} != {EXPECTED_EMBEDDING_DIM}"
                    )
            
            # Normalize embeddings for cosine similarity
            if normalize:
                embeddings = [normalize_embedding(emb) for emb in embeddings]
                logger.info(f"Generated and normalized {len(embeddings)} embeddings (dim={EXPECTED_EMBEDDING_DIM})")
            else:
                logger.info(f"Generated {len(embeddings)} embeddings (dim={EXPECTED_EMBEDDING_DIM}, not normalized)")
            
            return embeddings
            
        except openai.RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + (time.time() % 1)  # Exponential backoff with jitter
                logger.warning(f"Rate limit hit, retrying in {wait_time:.2f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                logger.error(f"Rate limit error after {max_retries} attempts: {e}")
                raise
                
        except openai.APIError as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt)
                logger.warning(f"API error, retrying in {wait_time:.2f}s (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"API error after {max_retries} attempts: {e}")
                raise
                
        except Exception as e:
            logger.error(f"Unexpected error generating embeddings: {e}")
            raise
    
    raise Exception("Failed to generate embeddings after all retries")
