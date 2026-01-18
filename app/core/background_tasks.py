"""Background task management using ThreadPoolExecutor."""
from concurrent.futures import ThreadPoolExecutor, Future
import logging
import threading
from typing import Callable, Any
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global thread pool executor for background tasks
# Queue limit is enforced manually since ThreadPoolExecutor doesn't support it directly
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ingestion-worker")
_pending_tasks = 0  # Thread-safe counter for queue size tracking
_pending_tasks_lock = threading.Lock()  # Lock for thread-safe counter updates


def submit_task(func: Callable, *args: Any, **kwargs: Any) -> None:
    """
    Submit a task to the background thread pool.
    
    Enforces queue limit to prevent unbounded memory growth.
    If queue is full, raises HTTPException with 503 SERVICE_UNAVAILABLE.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Raises:
        HTTPException: If queue is full (503 SERVICE_UNAVAILABLE)
    """
    global _pending_tasks
    
    # Thread-safe queue limit check and increment
    queue_limit = getattr(settings, 'background_task_queue_size', 50)
    
    with _pending_tasks_lock:
        if _pending_tasks >= queue_limit:
            logger.warning(f"Background task queue full ({_pending_tasks}/{queue_limit}), rejecting task")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Background task queue is full. Please try again later.",
                    "details": {"queue_size": _pending_tasks, "queue_limit": queue_limit}
                }
            )
        _pending_tasks += 1
    
    def _handle_exception(future: Future) -> None:
        """Handle exceptions from background tasks."""
        global _pending_tasks
        with _pending_tasks_lock:
            _pending_tasks = max(0, _pending_tasks - 1)  # Thread-safe decrement
        
        try:
            future.result()
        except Exception as e:
            logger.error(f"Background task failed: {e}", exc_info=True)
    
    future = _executor.submit(func, *args, **kwargs)
    future.add_done_callback(_handle_exception)


def shutdown_executor() -> None:
    """Shutdown the thread pool executor (for testing/cleanup)."""
    _executor.shutdown(wait=True)
