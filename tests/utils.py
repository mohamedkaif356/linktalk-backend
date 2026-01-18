"""Test utility functions."""
import hashlib
from typing import Optional


def create_device_token_hash(token: str) -> str:
    """Create a device token hash for testing."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_test_device_data(
    app_instance_id: str = "test-instance-id",
    device_model: str = "Test Device",
    os_version: str = "1.0",
    stable_device_id: Optional[str] = None
) -> dict:
    """Create test device registration data."""
    return {
        "app_instance_id": app_instance_id,
        "device_model": device_model,
        "os_version": os_version,
        "stable_device_id": stable_device_id
    }
