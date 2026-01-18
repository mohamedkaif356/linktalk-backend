"""Vector database service using Chroma."""
import chromadb
from chromadb.config import Settings
from typing import List
import logging

from app.core.config import settings
from app.services.chunker import Chunk
from app.services.embeddings import EXPECTED_EMBEDDING_DIM

logger = logging.getLogger(__name__)

# Global Chroma client
_client = None
_collection = None


def get_client() -> chromadb.PersistentClient:
    """Get or create Chroma client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_path)
    return _client


def get_collection() -> chromadb.Collection:
    """Get or create the rag_chunks collection with cosine similarity metric."""
    global _collection
    if _collection is None:
        client = get_client()
        try:
            _collection = client.get_collection(name="rag_chunks")
            # Verify metric is cosine (handle None metadata case)
            try:
                collection_metadata = _collection.metadata
                if collection_metadata is None:
                    collection_metadata = {}
                elif not isinstance(collection_metadata, dict):
                    collection_metadata = {}
                
                if collection_metadata.get("hnsw:space") != "cosine":
                    logger.warning("Collection exists but metric may not be cosine. Recreating...")
                    try:
                        client.delete_collection(name="rag_chunks")
                    except Exception:
                        pass
                    raise Exception("Recreate with cosine")
                logger.info("Retrieved existing rag_chunks collection with cosine metric")
            except (AttributeError, TypeError) as e:
                # Metadata access failed, recreate collection
                logger.warning(f"Could not read collection metadata ({e}), recreating...")
                try:
                    client.delete_collection(name="rag_chunks")
                except Exception:
                    pass
                raise Exception("Recreate with cosine")
        except Exception:
            _collection = client.create_collection(
                name="rag_chunks",
                metadata={
                    "description": "RAG chunks with embeddings",
                    "hnsw:space": "cosine"  # Explicit cosine similarity
                }
            )
            logger.info("Created new rag_chunks collection with cosine metric")
    return _collection


def store_chunks(ingestion_id: str, device_id: str, chunks: List[Chunk], embeddings: List[List[float]], url: str = None) -> None:
    """
    Store chunks with embeddings in Chroma.
    
    Args:
        ingestion_id: Ingestion ID
        device_id: Device ID
        chunks: List of Chunk objects
        embeddings: List of embedding vectors
        url: URL of the ingested content (optional, for metadata)
        
    Raises:
        ValueError: If chunk/embedding count mismatch or embedding dimension mismatch
    """
    if len(chunks) != len(embeddings):
        raise ValueError(f"Mismatch: {len(chunks)} chunks but {len(embeddings)} embeddings")
    
    # Validate embedding dimensions
    for i, emb in enumerate(embeddings):
        if len(emb) != EXPECTED_EMBEDDING_DIM:
            raise ValueError(
                f"Embedding {i} has wrong dimension: {len(emb)} != {EXPECTED_EMBEDDING_DIM}"
            )
    
    collection = get_collection()
    
    # Prepare data for Chroma
    ids = [f"{ingestion_id}_{chunk.position}" for chunk in chunks]
    texts = [chunk.text for chunk in chunks]
    metadatas = [
        {
            "ingestion_id": ingestion_id,
            "device_id": device_id,
            "position": chunk.position,
            "text_snippet": chunk.text[:200],  # Store snippet for debugging
            "url": url or ""  # Store URL for better organization and debugging
        }
        for chunk in chunks
    ]
    
    try:
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        logger.info(f"Stored {len(chunks)} chunks for ingestion {ingestion_id}")
    except Exception as e:
        logger.error(f"Failed to store chunks in Chroma: {e}")
        raise
