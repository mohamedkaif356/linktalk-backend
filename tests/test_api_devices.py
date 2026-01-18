"""Integration tests for device registration endpoints."""
import pytest
from fastapi import status
from app.db.models import Device, DeviceToken
import hashlib


class TestDeviceRegistration:
    """Test device registration API."""
    
    def test_register_new_device(self, client):
        """Test registering a new device."""
        response = client.post(
            "/api/v1/register-device",
            json={
                "app_instance_id": "test-instance-123",
                "device_model": "Test Device",
                "os_version": "1.0"
            }
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "device_token" in data
        assert "quota_remaining" in data
        assert data["quota_remaining"] == 3
        assert "device_fingerprint" in data
    
    def test_register_device_missing_field(self, client):
        """Test registration with missing required field."""
        response = client.post(
            "/api/v1/register-device",
            json={
                "device_model": "Test Device",
                "os_version": "1.0"
                # Missing app_instance_id
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "MISSING_FIELD"
    
    def test_register_device_idempotent(self, client):
        """Test that registering same device twice returns same quota."""
        device_data = {
            "app_instance_id": "test-instance-idempotent",
            "device_model": "Test Device",
            "os_version": "1.0"
        }
        
        # First registration
        response1 = client.post("/api/v1/register-device", json=device_data)
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        quota1 = data1["quota_remaining"]
        
        # Second registration (same device)
        response2 = client.post("/api/v1/register-device", json=device_data)
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        quota2 = data2["quota_remaining"]
        
        # Quota should be preserved
        assert quota1 == quota2
    
    def test_register_device_invalid_model_too_long(self, client):
        """Test registration with device model too long."""
        response = client.post(
            "/api/v1/register-device",
            json={
                "app_instance_id": "test-instance",
                "device_model": "a" * 201,  # Too long
                "os_version": "1.0"
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "INVALID_DEVICE_INFO"
    
    def test_register_device_with_stable_id(self, client):
        """Test registration with stable device ID."""
        response = client.post(
            "/api/v1/register-device",
            json={
                "app_instance_id": "test-instance",
                "device_model": "Test Device",
                "os_version": "1.0",
                "stable_device_id": "stable-id-123"
            }
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "device_token" in data
