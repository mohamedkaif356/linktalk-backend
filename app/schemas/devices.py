from pydantic import BaseModel, Field
from typing import Optional


class RegisterDeviceRequest(BaseModel):
    """Request schema for device registration."""
    
    app_instance_id: str = Field(..., description="UUID generated on app first launch")
    device_model: str = Field(..., description="Device model (e.g., 'Pixel 6')")
    os_version: str = Field(..., description="OS version (e.g., '14')")
    stable_device_id: Optional[str] = Field(
        None,
        description="Stable device identifier across reinstalls (optional)"
    )


class RegisterDeviceResponse(BaseModel):
    """Response schema for device registration."""
    
    device_token: str = Field(..., description="Opaque device token for authentication")
    quota_remaining: int = Field(..., description="Remaining queries for this device")
    device_fingerprint: str = Field(..., description="Server-computed device fingerprint")


class DeviceInfo(BaseModel):
    """Device information model."""
    
    device_id: str
    device_fingerprint: str
    quota_remaining: int
    device_model: str
    os_version: str
