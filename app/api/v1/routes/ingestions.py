"""Ingestion API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.db.session import get_db
from app.db.models import Ingestion, IngestionStatus, Device
from app.api.deps import get_current_device
from app.schemas.ingestions import ScrapeURLRequest, ScrapeURLResponse, IngestionStatusResponse
from app.services.url_validator import validate_url
from app.core.errors import InvalidURLError, InternalIPError, ForbiddenError, URLAlreadyIngestedError
from app.core.background_tasks import submit_task
from app.services.ingestion_worker import process_ingestion

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/scrape-url", response_model=ScrapeURLResponse)
async def scrape_url(
    request: ScrapeURLRequest,
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db)
):
    """
    Initiate URL scraping and ingestion.
    
    Validates the URL, checks if device already has a URL ingested (only one URL per device allowed),
    creates an ingestion record, and kicks off async processing.
    Returns immediately with ingestion_id for status polling.
    """
    # Check if device already has a successful ingestion (one URL per device limit)
    existing_ingestion = db.query(Ingestion).filter(
        Ingestion.device_id == device.id,
        Ingestion.status == IngestionStatus.SUCCESS
    ).first()
    
    if existing_ingestion:
        logger.warning(f"Device {device.id} attempted to ingest second URL: {request.url}. Existing URL: {existing_ingestion.url}")
        raise URLAlreadyIngestedError(existing_ingestion.url)
    
    # Validate URL
    try:
        validate_url(request.url)
    except InvalidURLError as e:
        raise e
    except InternalIPError as e:
        raise e
    
    # Create ingestion record
    ingestion = Ingestion(
        device_id=device.id,
        url=request.url,
        status=IngestionStatus.PENDING,
        estimated_time_seconds=20
    )
    
    db.add(ingestion)
    db.commit()
    db.refresh(ingestion)
    
    logger.info(f"Created ingestion {ingestion.id} for device {device.id}, URL: {request.url}")
    
    # Submit background task
    # Worker will create its own DB session for thread safety
    submit_task(process_ingestion, ingestion.id, request.url, device.id)
    
    return ScrapeURLResponse(
        ingestion_id=ingestion.id,
        status=ingestion.status.value,
        estimated_time_seconds=ingestion.estimated_time_seconds
    )


@router.get("/ingestions/{ingestion_id}", response_model=IngestionStatusResponse)
async def get_ingestion_status(
    ingestion_id: str,
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db)
):
    """
    Get ingestion status by ID.
    
    Only returns ingestion if it belongs to the requesting device.
    """
    ingestion = db.query(Ingestion).filter(Ingestion.id == ingestion_id).first()
    
    if not ingestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Ingestion {ingestion_id} not found",
                "details": {}
            }
        )
    
    # Check authorization: ingestion must belong to requesting device
    if ingestion.device_id != device.id:
        raise ForbiddenError("Ingestion belongs to a different device")
    
    return IngestionStatusResponse(
        id=ingestion.id,
        status=ingestion.status.value,
        url=ingestion.url,
        chunk_count=ingestion.chunk_count,
        token_count=ingestion.token_count,
        error_code=ingestion.error_code,
        error_message=ingestion.error_message,
        created_at=ingestion.created_at,
        started_at=ingestion.started_at,
        completed_at=ingestion.completed_at
    )
