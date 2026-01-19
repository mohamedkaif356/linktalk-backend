"""Tests for background task management."""
import pytest
from app.core.background_tasks import submit_task
from app.core.config import settings
from fastapi import HTTPException, status
import time


class TestBackgroundTasks:
    """Test background task submission."""
    
    def test_submit_task_success(self):
        """Test successful task submission."""
        def dummy_task():
            return "success"
        
        # Should not raise
        submit_task(dummy_task)
        time.sleep(0.2)  # Give task time to complete
    
    def test_submit_task_queue_full(self, monkeypatch):
        """Test task submission when queue is full."""
        import app.core.background_tasks as bg_tasks
        
        # Mock settings to have very small queue
        original_limit = settings.background_task_queue_size
        monkeypatch.setattr(settings, 'background_task_queue_size', 1)
        
        # Set pending tasks to limit (at the limit, so next submission should fail)
        with bg_tasks._pending_tasks_lock:
            bg_tasks._pending_tasks = 1  # Set to limit
        
        def dummy_task():
            time.sleep(0.1)
        
        try:
            with pytest.raises(HTTPException) as exc_info:
                submit_task(dummy_task)
            
            assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert exc_info.value.detail["code"] == "SERVICE_UNAVAILABLE"
            assert exc_info.value.detail["details"]["queue_size"] == 1
            assert exc_info.value.detail["details"]["queue_limit"] == 1
        finally:
            # Reset - wait a bit for any pending tasks to complete
            time.sleep(0.2)
            with bg_tasks._pending_tasks_lock:
                bg_tasks._pending_tasks = 0
            monkeypatch.setattr(settings, 'background_task_queue_size', original_limit)
    
    def test_submit_task_handles_exception(self):
        """Test that task exceptions are handled gracefully."""
        def failing_task():
            raise ValueError("Test error")
        
        # Should not raise, exception is logged
        submit_task(failing_task)
        time.sleep(0.2)  # Give task time to complete and callback to run
    
    def test_submit_task_executor_shutdown(self):
        """Test task submission when executor is shut down."""
        from app.core.background_tasks import _executor
        from concurrent.futures import ThreadPoolExecutor
        import app.core.background_tasks as bg_tasks
        
        # Save original executor
        original_executor = _executor
        
        # Create new executor and shut it down
        test_executor = ThreadPoolExecutor(max_workers=1)
        test_executor.shutdown(wait=True)
        
        # Temporarily replace executor
        bg_tasks._executor = test_executor
        
        def dummy_task():
            pass
        
        # Should handle gracefully without raising
        submit_task(dummy_task)
        
        # Restore original executor
        bg_tasks._executor = original_executor
