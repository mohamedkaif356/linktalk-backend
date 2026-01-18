"""Query API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.db.session import get_db
from app.db.models import Query, QueryStatus, Device, Ingestion
from app.api.deps import get_current_device
from app.schemas.queries import QueryRequest, QueryResponse, QueryStatusResponse, SourceInfo
from app.services.query_service import validate_question
from app.core.errors import InvalidQuestionError, QuotaExhaustedError, ForbiddenError
from app.core.background_tasks import submit_task
from app.services.query_worker import process_query

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db)
):
    """
    Submit a RAG query.
    
    Validates the question, checks quota, creates a query record, and kicks off async processing.
    Returns immediately with query_id for status polling.
    """
    # Check quota - worker will deduct atomically to prevent race conditions
    # This check prevents unnecessary query creation, but worker does final atomic deduction
    if device.quota_remaining <= 0:
        quota_used = 3 - device.quota_remaining
        logger.warning(f"Device {device.id} attempted query with exhausted quota (remaining: {device.quota_remaining})")
        raise QuotaExhaustedError(quota_used=quota_used, quota_total=3)
    
    logger.info(f"Device {device.id} submitting query. Quota remaining: {device.quota_remaining}/3")
    
    # Validate question
    try:
        validate_question(request.question)
    except InvalidQuestionError as e:
        raise e
    
    # Create query record
    query = Query(
        device_id=device.id,
        question=request.question,
        status=QueryStatus.PENDING,
        estimated_time_seconds=5
    )
    
    db.add(query)
    db.commit()
    db.refresh(query)
    
    logger.info(f"Created query {query.id} for device {device.id}, question: {request.question[:50]}...")
    
    # Submit background task
    # Worker will create its own DB session for thread safety
    submit_task(
        process_query,
        query.id,
        request.question,
        device.id,
        request.max_chunks or 5,
        request.temperature or 0.7
    )
    
    return QueryResponse(
        query_id=query.id,
        status=query.status.value,
        estimated_time_seconds=query.estimated_time_seconds
    )


@router.get("/queries/{query_id}", response_model=QueryStatusResponse)
async def get_query_status(
    query_id: str,
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db)
):
    """
    Get query status by ID.
    
    Only returns query if it belongs to the requesting device.
    """
    query = db.query(Query).filter(Query.id == query_id).first()
    
    if not query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Query {query_id} not found",
                "details": {}
            }
        )
    
    # Check authorization: query must belong to requesting device
    if query.device_id != device.id:
        raise ForbiddenError("Query belongs to a different device")
    
    # Build sources list from QueryChunk records
    sources = []
    for query_chunk in query.query_chunks:
        # Get ingestion URL
        url = "unknown"
        if query_chunk.ingestion_id:
            ingestion = db.query(Ingestion).filter(Ingestion.id == query_chunk.ingestion_id).first()
            if ingestion:
                url = ingestion.url
        
        source_info = SourceInfo(
            ingestion_id=query_chunk.ingestion_id or "unknown",
            url=url,
            chunk_id=query_chunk.chunk_id,
            relevance_score=float(query_chunk.relevance_score) if query_chunk.relevance_score else 0.0,
            text_snippet=query_chunk.text_snippet
        )
        sources.append(source_info)
    
    return QueryStatusResponse(
        id=query.id,
        question=query.question,
        answer=query.answer,
        status=query.status.value,
        chunk_count_used=query.chunk_count_used,
        token_count=query.token_count,
        sources=sources,
        error_code=query.error_code,
        error_message=query.error_message,
        created_at=query.created_at,
        completed_at=query.completed_at
    )
