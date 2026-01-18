"""Pydantic schemas for ingestion endpoints."""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime


class ScrapeURLRequest(BaseModel):
    """Request schema for scraping a URL."""
    url: str = Field(..., description="URL to scrape and ingest")


class ScrapeURLResponse(BaseModel):
    """Response schema for scrape URL endpoint."""
    ingestion_id: str = Field(..., description="Unique ingestion ID")
    status: str = Field(..., description="Current status (PENDING)")
    estimated_time_seconds: int = Field(default=20, description="Estimated processing time")


class IngestionStatusResponse(BaseModel):
    """Response schema for ingestion status endpoint."""
    id: str
    status: str
    url: str
    chunk_count: Optional[int] = None
    token_count: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
