from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import uuid
import time

from app.api.v1.routes import devices, ingestions, queries
from app.core.config import settings
from app.core.background_tasks import shutdown_executor
from app.core.logging_config import setup_logging

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan: startup and shutdown.
    
    Ensures graceful shutdown of background task executor on application stop.
    Validates required environment variables on startup.
    Initializes database tables if they don't exist.
    """
    # Startup
    logger.info("Starting RAG Backend API...")
    
    # Validate required environment variables
    try:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required but not set")
        logger.info("Environment variables validated successfully")
    except Exception as e:
        logger.error(f"Startup validation failed: {e}")
        logger.error("Please set required environment variables. See .env.example for reference.")
        raise
    
    # Initialize database tables
    try:
        from app.db.init_db import init_db
        init_db()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        # Don't raise - allow app to start even if DB init fails
        # This allows for manual initialization if needed
    
    logger.info(f"Application starting in {settings.environment} mode")
    yield
    
    # Shutdown
    logger.info("Shutting down RAG Backend API...")
    shutdown_executor()
    logger.info("Background executor shut down")


# Create FastAPI app with lifespan
app = FastAPI(
    title="RAG Backend API",
    description="Backend API for RAG-based chat application",
    version="1.0.0",
    lifespan=lifespan
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Convert Pydantic validation errors to our error format."""
    errors = exc.errors()
    if errors:
        first_error = errors[0]
        field_name = first_error.get("loc", ["unknown"])[-1] if first_error.get("loc") else "unknown"
        
        # Check if it's a missing field
        if first_error.get("type") == "missing":
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "detail": {
                        "code": "MISSING_FIELD",
                        "message": f"Missing required field: {field_name}",
                        "details": {"field": field_name}
                    }
                }
            )
    
    # Fallback to default validation error format
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors}
    )

# Add request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request for traceability."""
    request_id = str(uuid.uuid4())[:8]
    
    # Add request ID to request state
    request.state.request_id = request_id
    
    # Add request ID to logger context
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = request_id
        return record
    logging.setLogRecordFactory(record_factory)
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(round(process_time, 3))
    
    # Restore original factory
    logging.setLogRecordFactory(old_factory)
    
    return response

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For MVP, allow all origins
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(devices.router, prefix="/api/v1", tags=["devices"])
app.include_router(ingestions.router, prefix="/api/v1", tags=["ingestions"])
app.include_router(queries.router, prefix="/api/v1", tags=["queries"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "RAG Backend API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """
    Health check endpoint with dependency verification.
    
    Returns:
        - 200: All systems healthy
        - 503: System degraded or unhealthy
    """
    from sqlalchemy import text
    from app.db.session import SessionLocal
    import time
    
    health_status = {
        "status": "healthy",
        "database": {"status": "ok", "latency_ms": 0},
        "vector_db": {"status": "unknown", "latency_ms": 0},
        "openai": {"status": "unknown", "latency_ms": 0}
    }
    
    # Check database connectivity with latency
    try:
        start = time.time()
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        latency = (time.time() - start) * 1000
        health_status["database"] = {"status": "ok", "latency_ms": round(latency, 2)}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = {"status": "error", "error": str(e)}
        logger.error(f"Database health check failed: {e}")
    
    # Check Chroma connectivity with latency
    try:
        start = time.time()
        from app.services.vector_db import get_collection
        collection = get_collection()
        collection.count()
        latency = (time.time() - start) * 1000
        health_status["vector_db"] = {"status": "ok", "latency_ms": round(latency, 2)}
    except Exception as e:
        health_status["vector_db"] = {"status": "error", "error": str(e)}
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"
        logger.warning(f"Vector DB health check failed: {e}")
    
    # Check OpenAI API key (lightweight check - just verify it's set)
    try:
        if settings.openai_api_key and len(settings.openai_api_key) > 10:
            health_status["openai"] = {"status": "configured", "latency_ms": 0}
        else:
            health_status["openai"] = {"status": "not_configured", "error": "API key missing or invalid"}
            if health_status["status"] == "healthy":
                health_status["status"] = "degraded"
    except Exception as e:
        health_status["openai"] = {"status": "error", "error": str(e)}
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"
    
    # Determine HTTP status code
    status_code = 200 if health_status["status"] == "healthy" else 503
    
    return JSONResponse(content=health_status, status_code=status_code)
