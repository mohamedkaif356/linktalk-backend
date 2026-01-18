"""Async ingestion worker for processing URLs."""
import logging
import time
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models import Ingestion, IngestionStatus
from app.services.scraper import fetch_html, extract_readable_content, truncate_text, estimate_tokens
from app.services.chunker import chunk_text
from app.services.embeddings import generate_embeddings
from app.services.vector_db import store_chunks
from app.core.config import settings
from app.core.errors import ScrapingError

logger = logging.getLogger(__name__)


def process_ingestion(ingestion_id: str, url: str, device_id: str, db_session: Session = None) -> None:
    """
    Process an ingestion: fetch, extract, chunk, embed, and store.
    
    This function runs in a background thread and updates the ingestion status.
    Creates its own database session for thread safety.
    
    Args:
        ingestion_id: Ingestion ID
        url: URL to process
        device_id: Device ID
        db_session: Optional database session (will create new one if None)
    """
    from app.db.session import SessionLocal
    
    # Create new session for thread safety
    db = db_session or SessionLocal()
    
    # Track start time for timeout enforcement
    start_time = time.time()
    task_timeout = getattr(settings, 'ingestion_task_timeout_seconds', 300)  # 5 minutes default
    
    try:
        # Update status to PROCESSING
        ingestion = db.query(Ingestion).filter(Ingestion.id == ingestion_id).first()
        if not ingestion:
            logger.error(f"Ingestion {ingestion_id} not found")
            return
        
        ingestion.status = IngestionStatus.PROCESSING
        ingestion.started_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Starting ingestion {ingestion_id} for URL: {url}")
        logger.info(f"[STEP 1/6] Fetching HTML from URL")
        logger.debug(f"Fetching HTML from {url}")
        html = fetch_html(url)
        logger.info(f"HTML fetched: {len(html)} characters")
        
        # Step 2: Extract readable content
        logger.info(f"[STEP 2/6] Extracting readable content")
        logger.debug("Extracting readable content")
        text = extract_readable_content(html)
        logger.info(f"Content extracted: {len(text)} characters")
        logger.debug(f"Text preview (first 300 chars): {text[:300]}...")
        
        # Step 3: Truncate if needed
        logger.info(f"[STEP 3/6] Checking token count and truncating if needed")
        token_count = estimate_tokens(text)
        logger.debug(f"Estimated tokens: {token_count}")
        if token_count > settings.max_tokens:
            logger.warning(f"Text exceeds max tokens ({token_count} > {settings.max_tokens}), truncating")
            text = truncate_text(text, settings.max_tokens)
            token_count = estimate_tokens(text)
            logger.info(f"Truncated to {token_count} tokens")
        else:
            logger.debug(f"Within limit ({token_count} <= {settings.max_tokens})")
        
        # Step 4: Chunk text
        logger.info(f"[STEP 4/6] Chunking text")
        logger.debug("Chunking text")
        chunks = chunk_text(text)
        logger.info(f"Created {len(chunks)} chunks")
        # Log chunk details at debug level
        for i, chunk in enumerate(chunks[:5], 1):
            logger.debug(f"Chunk {i}: {chunk.token_count} tokens, {len(chunk.text)} chars, preview: {chunk.text[:100]}...")
        if len(chunks) > 5:
            logger.debug(f"... and {len(chunks) - 5} more chunks")
        
        if not chunks:
            raise ScrapingError("NO_CONTENT", "No chunks created from extracted text")
        
        # Check timeout before embedding generation (most time-consuming step)
        elapsed = time.time() - start_time
        if elapsed > task_timeout:
            raise ScrapingError(
                "TASK_TIMEOUT",
                f"Ingestion exceeded maximum time limit ({task_timeout} seconds). The URL may be too large or processing too slow."
            )
        
        # Step 5: Generate embeddings
        logger.info(f"[STEP 5/6] Generating embeddings with OpenAI")
        logger.debug("Generating embeddings")
        chunk_texts = [chunk.text for chunk in chunks]
        logger.info(f"Sending {len(chunk_texts)} chunks to OpenAI API")
        embeddings = generate_embeddings(chunk_texts)
        logger.info(f"Embeddings generated: {len(embeddings)} vectors")
        
        # Step 6: Store in Chroma
        logger.info(f"[STEP 6/6] Storing chunks in Chroma vector DB")
        logger.debug("Storing chunks in vector DB")
        store_chunks(ingestion_id, device_id, chunks, embeddings, url=url)
        logger.info(f"Stored {len(chunks)} chunks in Chroma")
        
        # Step 7: Update status to SUCCESS
        logger.info(f"[STEP 7/7] Updating database status")
        ingestion.status = IngestionStatus.SUCCESS
        ingestion.completed_at = datetime.utcnow()
        ingestion.chunk_count = len(chunks)
        ingestion.token_count = token_count
        ingestion.error_code = None
        ingestion.error_message = None
        db.commit()
        
        logger.info(f"Ingestion {ingestion_id} completed successfully: {len(chunks)} chunks, {token_count} tokens")
        
    except ScrapingError as e:
        logger.error(f"Ingestion {ingestion_id} failed with error {e.error_code}: {e.message}")
        try:
            _update_failed_status(db, ingestion_id, e.error_code, e.message)
            db.commit()
        except Exception as commit_error:
            logger.error(f"Failed to commit failed status: {commit_error}")
            db.rollback()
        
    except Exception as e:
        logger.error(f"Unexpected error processing ingestion {ingestion_id}: {e}", exc_info=True)
        error_msg = str(e)
        if "quota" in error_msg.lower():
            logger.warning("This appears to be an OpenAI API quota issue. Scraping and chunking may have completed successfully, but embedding generation failed due to quota limits.")
        try:
            _update_failed_status(db, ingestion_id, "UNKNOWN_ERROR", error_msg)
            db.commit()
        except Exception as commit_error:
            logger.error(f"Failed to commit failed status: {commit_error}")
            db.rollback()
    finally:
        # Close session if we created it
        if db_session is None:
            db.close()


def _update_failed_status(db: Session, ingestion_id: str, error_code: str, error_message: str) -> None:
    """Update ingestion status to FAILED."""
    try:
        ingestion = db.query(Ingestion).filter(Ingestion.id == ingestion_id).first()
        if ingestion:
            ingestion.status = IngestionStatus.FAILED
            ingestion.completed_at = datetime.utcnow()
            ingestion.error_code = error_code
            ingestion.error_message = error_message
            db.commit()
            logger.info(f"Updated ingestion {ingestion_id} to FAILED: {error_code}")
    except Exception as e:
        logger.error(f"Failed to update ingestion status: {e}", exc_info=True)
