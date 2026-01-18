"""Pydantic schemas for query requests and responses."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SourceInfo(BaseModel):
    """Source information for a query answer."""
    ingestion_id: str
    url: str
    chunk_id: str
    relevance_score: float
    text_snippet: str


class QueryRequest(BaseModel):
    """Request schema for submitting a query."""
    question: str = Field(..., min_length=10, max_length=500, description="The question to ask")
    max_chunks: Optional[int] = Field(default=5, ge=1, le=10, description="Maximum number of chunks to retrieve")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="Temperature for answer generation")


class QueryResponse(BaseModel):
    """Response schema for query submission."""
    query_id: str
    status: str
    estimated_time_seconds: int


class QueryStatusResponse(BaseModel):
    """Response schema for query status."""
    id: str
    question: str
    answer: Optional[str] = None
    status: str
    chunk_count_used: Optional[int] = None
    token_count: Optional[int] = None
    sources: List[SourceInfo] = []
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
