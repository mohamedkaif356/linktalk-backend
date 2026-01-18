"""Query processing worker for background RAG queries."""
import logging
import time
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import update

from app.db.models import Query, QueryStatus, QueryChunk, Device, Ingestion, IngestionStatus
from app.services.query_service import embed_query, search_relevant_chunks, assemble_context
from app.services.llm_service import generate_answer
from app.services.rag_metrics import log_query_metrics
from app.core.config import settings
from app.core.errors import NoContentError, QueryGenerationError

logger = logging.getLogger(__name__)


def process_query(
    query_id: str,
    question: str,
    device_id: str,
    max_chunks: int = 5,
    temperature: float = 0.7,
    db_session: Session = None
) -> None:
    """
    Process a RAG query: embed, search, assemble context, generate answer.
    
    This function runs in a background thread and updates the query status.
    Creates its own database session for thread safety.
    
    Args:
        query_id: Query ID
        question: User's question
        device_id: Device ID
        max_chunks: Maximum chunks to retrieve
        temperature: Temperature for answer generation
        db_session: Optional database session (will create new one if None)
    """
    from app.db.session import SessionLocal
    
    # Create new session for thread safety
    db = db_session or SessionLocal()
    
    # Track start time for timeout enforcement
    start_time = time.time()
    task_timeout = getattr(settings, 'query_task_timeout_seconds', 120)  # 2 minutes default
    
    try:
        # Update status to PROCESSING
        query = db.query(Query).filter(Query.id == query_id).first()
        if not query:
            logger.error(f"Query {query_id} not found")
            return
        
        query.status = QueryStatus.PROCESSING
        query.started_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Starting query {query_id} for device {device_id}: {question[:50]}...")
        logger.info(f"[STEP 1/6] Getting device's ingested URL")
        ingestion = db.query(Ingestion).filter(
            Ingestion.device_id == device_id,
            Ingestion.status == IngestionStatus.SUCCESS
        ).first()
        
        if not ingestion:
            logger.warning(f"No successful ingestion found for device {device_id}")
            raise NoContentError("No ingested content available for this device. Please scrape a URL first.")
        
        logger.info(f"Found ingestion: {ingestion.url}")
        
        # Check timeout
        elapsed = time.time() - start_time
        if elapsed > task_timeout:
            raise QueryGenerationError(
                "TASK_TIMEOUT",
                f"Query exceeded maximum time limit ({task_timeout} seconds). Please try a simpler question."
            )
        
        # Step 2: Embed query
        logger.info(f"[STEP 2/6] Embedding query")
        logger.debug("Embedding query")
        query_embedding = embed_query(question)
        logger.info(f"Query embedded: {len(query_embedding)} dimensions")
        
        # Step 3: Search relevant chunks (filtered by device_id + ingestion_id + similarity threshold)
        logger.info(f"[STEP 3/6] Searching relevant chunks")
        logger.debug("Searching relevant chunks")
        
        # Get similarity threshold from config
        min_similarity = getattr(settings, 'min_similarity_threshold', 0.6) if settings.similarity_filter_enabled else 0.0
        logger.debug(f"Similarity threshold: {min_similarity}")
        
        try:
            chunks = search_relevant_chunks(query_embedding, device_id, ingestion.id, max_chunks, min_similarity=min_similarity)
            logger.info(f"Found {len(chunks)} relevant chunks (similarity >= {min_similarity})")
            
            if not chunks:
                # No chunks passed similarity threshold - return refusal
                refusal_message = f"No relevant content found with similarity >= {min_similarity}. The context does not contain information relevant to this question."
                raise NoContentError(refusal_message)
        except NoContentError as e:
            # Check if it's a threshold failure
            error_msg = str(e)
            if "similarity" in error_msg.lower() or "No chunks found with similarity" in error_msg:
                # This is a similarity threshold failure - return refusal response
                refusal_message = f"I cannot answer this question based on the provided context. The context does not contain information relevant to this question (no chunks found with similarity >= {min_similarity})."
                query.status = QueryStatus.SUCCESS
                query.answer = refusal_message
                query.chunk_count_used = 0
                query.token_count = 0
                query.completed_at = datetime.utcnow()
                query.error_code = "INSUFFICIENT_RELEVANCE"
                query.error_message = f"No chunks found with similarity >= {min_similarity}"
                db.commit()
                
                # Log metrics for refusal
                log_query_metrics(
                    query_id=query_id,
                    question=question,
                    chunks_retrieved=0,
                    chunks_after_threshold=0,
                    similarity_scores=[],
                    token_count=0,
                    answer_length=len(refusal_message),
                    refused=True,
                    error_code="INSUFFICIENT_RELEVANCE"
                )
                
                logger.warning(f"Query {query_id} refused due to insufficient relevance (threshold: {min_similarity})")
                logger.info(f"Refusal message: {refusal_message}")
                return
            raise
        
        # Step 4: Assemble context
        logger.info(f"[STEP 4/6] Assembling context")
        logger.debug("Assembling context")
        context, context_tokens = assemble_context(chunks)
        logger.info(f"Context assembled: {len(context)} characters, ~{context_tokens} tokens")
        
        # Check timeout before LLM call (most time-consuming step)
        elapsed = time.time() - start_time
        if elapsed > task_timeout:
            raise QueryGenerationError(
                "TASK_TIMEOUT",
                f"Query exceeded maximum time limit ({task_timeout} seconds). Please try a simpler question."
            )
        
        # Step 5: Generate answer
        logger.info(f"[STEP 5/6] Generating answer with OpenAI")
        logger.debug("Generating answer")
        answer, llm_token_count = generate_answer(question, context, temperature, strict_mode=settings.enable_strict_refusal)
        logger.info(f"Answer generated: {len(answer)} characters, {llm_token_count} tokens")
        logger.debug(f"Answer preview: {answer[:200]}...")
        
        # Step 6: Store QueryChunk records
        logger.info(f"[STEP 6/7] Storing source chunks")
        logger.debug("Storing QueryChunk records")
        
        # Get ingestion URLs for source attribution (if needed later)
        ingestion_ids = [chunk.get('ingestion_id') for chunk in chunks if chunk.get('ingestion_id')]
        if ingestion_ids:
            ingestions = db.query(Ingestion).filter(Ingestion.id.in_(ingestion_ids)).all()
            ingestion_url_map = {ing.id: ing.url for ing in ingestions}
        
        query_chunks = []
        for i, chunk in enumerate(chunks):
            ingestion_id = chunk.get('ingestion_id', '')
            chunk_id = chunk.get('chunk_id', '')
            document = chunk.get('document', '')
            # Use similarity score (0-1 range) if available, otherwise calculate from distance
            similarity = chunk.get('similarity')
            if similarity is None:
                # Fallback: convert distance to similarity (for backward compatibility)
                distance = chunk.get('distance', 1.0)
                cosine_similarity = 1.0 - distance
                similarity = (cosine_similarity + 1.0) / 2.0  # Normalize to 0-1
            
            query_chunk = QueryChunk(
                query_id=query_id,
                chunk_id=chunk_id,
                ingestion_id=ingestion_id if ingestion_id else None,
                relevance_score=str(similarity),  # Use similarity score (0-1 range, higher = more relevant)
                position=i,
                text_snippet=document[:200]
            )
            query_chunks.append(query_chunk)
        
        db.add_all(query_chunks)
        logger.info(f"Stored {len(query_chunks)} source chunks")
        
        # Step 7: Update Query record and deduct quota
        logger.info(f"[STEP 7/7] Updating query status and deducting quota")
        logger.debug("Updating query status")
        
        # Use actual token count from LLM response
        token_count = llm_token_count
        
        query.status = QueryStatus.SUCCESS
        query.answer = answer
        query.chunk_count_used = len(chunks)
        query.token_count = token_count
        query.completed_at = datetime.utcnow()
        query.error_code = None
        query.error_message = None
        
        # Deduct quota atomically (3 queries total per device)
        # Use atomic update with WHERE clause to prevent race conditions
        result = db.execute(
            update(Device)
            .where(Device.id == device_id, Device.quota_remaining > 0)
            .values(quota_remaining=Device.quota_remaining - 1)
        )
        
        if result.rowcount == 0:
            # Quota was already exhausted (shouldn't happen if API check is correct, but handle gracefully)
            logger.warning(f"Quota already exhausted for device {device_id} (atomic update returned 0 rows)")
        else:
            # Get updated quota for logging
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                logger.info(f"Deducted quota for device {device_id}: quota_remaining={device.quota_remaining} (3 queries total per device)")
        
        db.commit()
        
        # Log metrics for successful query
        similarity_scores = [chunk.get('similarity', 0.0) for chunk in chunks]
        log_query_metrics(
            query_id=query_id,
            question=question,
            chunks_retrieved=len(chunks),  # After threshold filtering
            chunks_after_threshold=len(chunks),
            similarity_scores=similarity_scores,
            token_count=token_count,
            answer_length=len(answer),
            refused=False,
            error_code=None
        )
        
        avg_similarity = sum(similarity_scores)/len(similarity_scores) if similarity_scores else 0.0
        logger.info(f"Query {query_id} completed successfully: {len(chunks)} chunks, {token_count} tokens, avg similarity: {avg_similarity:.3f}, quota remaining: {device.quota_remaining if device else 'N/A'}")
        
    except NoContentError as e:
        logger.error(f"Query {query_id} failed: NO_CONTENT - {e}")
        try:
            _update_failed_status(db, query_id, "NO_CONTENT", "No ingested content available for this device")
            db.commit()
        except Exception as commit_error:
            logger.error(f"Failed to commit failed status: {commit_error}")
            db.rollback()
        
    except QueryGenerationError as e:
        logger.error(f"Query {query_id} failed: {e.error_code} - {e.message}")
        try:
            _update_failed_status(db, query_id, e.error_code, e.message)
            db.commit()
        except Exception as commit_error:
            logger.error(f"Failed to commit failed status: {commit_error}")
            db.rollback()
        
    except Exception as e:
        logger.error(f"Unexpected error processing query {query_id}: {e}", exc_info=True)
        error_msg = str(e)
        try:
            _update_failed_status(db, query_id, "UNKNOWN_ERROR", error_msg)
            db.commit()
        except Exception as commit_error:
            logger.error(f"Failed to commit failed status: {commit_error}")
            db.rollback()
    finally:
        # Close session if we created it
        if db_session is None:
            db.close()


def _update_failed_status(db: Session, query_id: str, error_code: str, error_message: str) -> None:
    """Update query status to FAILED."""
    try:
        query = db.query(Query).filter(Query.id == query_id).first()
        if query:
            query.status = QueryStatus.FAILED
            query.completed_at = datetime.utcnow()
            query.error_code = error_code
            query.error_message = error_message
            db.commit()
            logger.info(f"Updated query {query_id} to FAILED: {error_code}")
    except Exception as e:
        logger.error(f"Failed to update query status: {e}", exc_info=True)
