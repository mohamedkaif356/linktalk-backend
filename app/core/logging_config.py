"""Centralized logging configuration for the application."""
import logging
import sys
import json
from typing import Any, Dict
from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging (production)."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add request ID if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter for console (development)."""
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console."""
        # Add request ID to message if present
        if hasattr(record, "request_id"):
            record.msg = f"[{record.request_id}] {record.msg}"
        return super().format(record)


def setup_logging() -> None:
    """
    Configure application logging based on environment.
    
    - Development: Console formatter with DEBUG level
    - Production: JSON formatter with INFO level
    """
    # Determine log level based on environment
    if settings.environment == "development":
        log_level = logging.DEBUG
        formatter = ConsoleFormatter()
    else:
        log_level = logging.INFO
        formatter = JSONFormatter()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    
    # Set levels for third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    logging.info(f"Logging configured: environment={settings.environment}, level={logging.getLevelName(log_level)}")
