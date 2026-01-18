"""Query service for RAG functionality."""
import logging
from typing import List, Dict
import tiktoken

from app.services.embeddings import generate_embeddings
from app.services.vector_db import get_collection
from app.core.config import settings
from app.core.errors import InvalidQuestionError, NoContentError

logger = logging.getLogger(__name__)

# Initialize tiktoken encoder for token counting
_encoder = tiktoken.encoding_for_model("gpt-4o-mini")


def validate_question(question: str) -> None:
    """
    Validate question format.
    
    Args:
        question: Question to validate
        
    Raises:
        InvalidQuestionError: If question is invalid
    """
    if not question or not question.strip():
        raise InvalidQuestionError("Question cannot be empty")
    
    question = question.strip()
    
    if len(question) < settings.min_query_length:
        raise InvalidQuestionError(f"Question must be at least {settings.min_query_length} characters")
    
    if len(question) > settings.max_query_length:
        raise InvalidQuestionError(f"Question must be at most {settings.max_query_length} characters")


def embed_query(question: str) -> List[float]:
    """
    Generate normalized embedding for a query question.
    
    Args:
        question: User's question
        
    Returns:
        Normalized embedding vector (list of floats, unit length)
    """
    # normalize=True ensures embeddings are normalized for cosine similarity
    embeddings = generate_embeddings([question], normalize=True)
    if not embeddings:
        raise ValueError("Failed to generate embedding for question")
    return embeddings[0]  # Already normalized


def search_relevant_chunks(
    query_embedding: List[float], 
    device_id: str, 
    ingestion_id: str, 
    max_chunks: int = 5,
    min_similarity: float = None
) -> List[Dict]:
    """
    Search Chroma for relevant chunks filtered by device_id AND ingestion_id (URL-specific).
    
    This ensures queries only search chunks from the device's ingested URL.
    Converts cosine distance to similarity score (0-1 range) and filters by threshold.
    
    Args:
        query_embedding: Normalized query embedding vector
        device_id: Device ID to filter chunks
        ingestion_id: Ingestion ID (URL-specific) to filter chunks
        max_chunks: Maximum number of chunks to retrieve
        min_similarity: Minimum similarity threshold (0-1). If None, uses config default.
        
    Returns:
        List of chunk dictionaries with: chunk_id, ingestion_id, document, metadata, 
        distance, similarity (sorted by similarity descending)
        
    Raises:
        NoContentError: If no chunks found for device/ingestion or no chunks pass threshold
    """
    # Import here to avoid circular dependency
    from app.core.config import settings
    
    if min_similarity is None:
        min_similarity = getattr(settings, 'min_similarity_threshold', 0.0)
    
    collection = get_collection()
    
    try:
        # Query with device_id (Chroma doesn't support multiple conditions in where clause)
        # Since we enforce one URL per device, querying by device_id is sufficient
        # We'll also verify ingestion_id matches for safety
        results = collection.query(
            query_embeddings=[query_embedding],
            where={"device_id": device_id},
            n_results=max_chunks * 3,  # Get more results to filter by ingestion_id and similarity
            include=['documents', 'metadatas', 'distances']
        )
        
        if not results or not results.get('ids') or not results['ids'][0]:
            logger.warning(f"No chunks found for device {device_id}")
            raise NoContentError()
        
        # Process results, filter by ingestion_id, and convert distance to similarity
        chunks = []
        for i in range(len(results['ids'][0])):
            chunk_ingestion_id = results['metadatas'][0][i].get('ingestion_id', '')
            # Only include chunks that match the ingestion_id
            if chunk_ingestion_id != ingestion_id:
                continue
            
            distance = results['distances'][0][i] if results.get('distances') and results['distances'][0] else 2.0
            
            # Convert cosine distance to similarity score
            # Chroma's cosine distance: distance = 1 - cosine_similarity
            # So: cosine_similarity = 1 - distance (range: -1 to 1 for normalized vectors)
            # Normalize to 0-1 range: similarity_01 = (cosine_similarity + 1) / 2
            cosine_similarity = 1.0 - distance  # Range: -1 to 1
            similarity_01 = (cosine_similarity + 1.0) / 2.0  # Range: 0 to 1
            
            # Filter by similarity threshold
            if similarity_01 < min_similarity:
                logger.debug(f"Chunk {i} filtered: similarity {similarity_01:.3f} < {min_similarity}")
                continue
            
            chunk_data = {
                'chunk_id': results['ids'][0][i],
                'ingestion_id': chunk_ingestion_id,
                'document': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': distance,
                'similarity': similarity_01  # Add similarity score (0-1 range)
            }
            chunks.append(chunk_data)
        
        if not chunks:
            logger.warning(f"No chunks found for device {device_id} and ingestion {ingestion_id} with similarity >= {min_similarity}")
            raise NoContentError(f"No chunks found with similarity >= {min_similarity}")
        
        # Sort by similarity descending (highest first)
        chunks.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Limit to max_chunks
        chunks = chunks[:max_chunks]
        
        logger.info(f"Retrieved {len(chunks)} chunks for device {device_id} and ingestion {ingestion_id} (similarity >= {min_similarity})")
        return chunks
        
    except NoContentError:
        raise
    except Exception as e:
        logger.error(f"Error searching chunks: {e}")
        raise NoContentError() from e


def assemble_context(
    chunks: List[Dict], 
    max_tokens: int = None,
    snippet_chars: int = None
) -> tuple[str, int]:
    """
    Assemble context string from retrieved chunks with smart token budgeting.
    Uses snippet compression for lower-relevance chunks.
    
    Args:
        chunks: List of chunk dictionaries (already sorted by similarity descending)
        max_tokens: Maximum tokens for context (default from config)
        snippet_chars: Maximum characters for snippets (default from config)
        
    Returns:
        Tuple of (formatted context string, actual token count)
    """
    if max_tokens is None:
        max_tokens = settings.max_context_tokens
    if snippet_chars is None:
        snippet_chars = getattr(settings, 'snippet_max_chars', 150)
    
    context_parts = []
    total_tokens = 0
    
    # Chunks are already sorted by similarity descending
    for i, chunk in enumerate(chunks):
        similarity = chunk.get('similarity', 0.0)
        ingestion_id = chunk.get('ingestion_id', 'unknown')
        document = chunk.get('document', '')
        
        # For lower similarity chunks (after top 3), use snippet instead of full text
        if similarity < 0.7 and i > 2:
            if len(document) > snippet_chars:
                document = document[:snippet_chars] + "..."
            chunk_text = f"[Source {i+1} (relevance: {similarity:.2f})]\n{document}\n"
        else:
            chunk_text = f"[Source {i+1} (relevance: {similarity:.2f})]\n{document}\n"
        
        # Estimate tokens
        chunk_tokens = len(_encoder.encode(chunk_text))
        
        # Check if adding this chunk would exceed limit
        if total_tokens + chunk_tokens > max_tokens:
            logger.info(f"Context truncated: {total_tokens} tokens used, {len(context_parts)} chunks included")
            break
        
        context_parts.append(chunk_text)
        total_tokens += chunk_tokens
    
    context = "\n---\n".join(context_parts)
    logger.info(f"Assembled context: {len(context)} chars, ~{total_tokens} tokens")
    return context, total_tokens
