from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
import hashlib
import secrets
from datetime import datetime

from app.db.session import get_db
from app.db.models import Device, DeviceToken
from app.schemas.devices import RegisterDeviceRequest, RegisterDeviceResponse
from app.core.config import settings
from app.core.errors import MissingFieldError, InvalidDeviceInfoError

router = APIRouter()


def compute_device_fingerprint(
    app_instance_id: str,
    device_model: str,
    os_version: str,
    stable_device_id: Optional[str] = None
) -> str:
    """
    Compute device fingerprint from device information.
    
    Uses stable_device_id if provided, otherwise falls back to app_instance_id.
    """
    fingerprint_source = stable_device_id if stable_device_id else app_instance_id
    
    # Create fingerprint string
    fingerprint_string = f"{settings.device_fingerprint_salt}:{fingerprint_source}:{device_model}:{os_version}"
    
    # Hash it
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()


def generate_device_token() -> str:
    """Generate a secure random opaque token."""
    return secrets.token_urlsafe(32)


@router.post("/register-device", response_model=RegisterDeviceResponse)
async def register_device(
    request: RegisterDeviceRequest,
    db: Session = Depends(get_db)
):
    """
    Register a device and return a device token.
    
    This endpoint is idempotent: calling it multiple times with the same
    device information will return the same device and quota (won't reset).
    """
    # Validate required fields
    if not request.app_instance_id:
        raise MissingFieldError("app_instance_id")
    if not request.device_model:
        raise MissingFieldError("device_model")
    if not request.os_version:
        raise MissingFieldError("os_version")
    
    # Validate device info format (basic checks)
    if len(request.device_model) > 200:
        raise InvalidDeviceInfoError("device_model too long (max 200 chars)")
    if len(request.os_version) > 50:
        raise InvalidDeviceInfoError("os_version too long (max 50 chars)")
    
    # Compute device fingerprint
    device_fingerprint = compute_device_fingerprint(
        request.app_instance_id,
        request.device_model,
        request.os_version,
        request.stable_device_id
    )
    
    # Check if device already exists
    existing_device = db.query(Device).filter(
        Device.device_fingerprint == device_fingerprint
    ).first()
    
    if existing_device:
        # Device exists - return existing token or create new one
        # Find an active token for this device
        active_token = db.query(DeviceToken).filter(
            DeviceToken.device_id == existing_device.id,
            DeviceToken.revoked_at.is_(None)
        ).first()
        
        if active_token:
            # Return existing token (we need to return the original token, not hash)
            # Since we only store hash, we can't return the original token
            # For MVP, we'll generate a new token but keep the same quota
            # In production, you'd want to store tokens encrypted or use a token store
            device_token = generate_device_token()
            token_hash = hashlib.sha256(device_token.encode()).hexdigest()
            
            # Create new token entry
            new_token = DeviceToken(
                token_hash=token_hash,
                device_id=existing_device.id,
                created_at=datetime.utcnow()
            )
            db.add(new_token)
            db.commit()
            
            return RegisterDeviceResponse(
                device_token=device_token,
                quota_remaining=existing_device.quota_remaining,
                device_fingerprint=existing_device.device_fingerprint
            )
        else:
            # No active token, create new one
            device_token = generate_device_token()
            token_hash = hashlib.sha256(device_token.encode()).hexdigest()
            
            new_token = DeviceToken(
                token_hash=token_hash,
                device_id=existing_device.id,
                created_at=datetime.utcnow()
            )
            db.add(new_token)
            db.commit()
            
            return RegisterDeviceResponse(
                device_token=device_token,
                quota_remaining=existing_device.quota_remaining,
                device_fingerprint=existing_device.device_fingerprint
            )
    else:
        # New device - create it
        new_device = Device(
            device_fingerprint=device_fingerprint,
            quota_remaining=3,
            device_model=request.device_model,
            os_version=request.os_version
        )
        
        try:
            db.add(new_device)
            db.flush()  # Get the device ID
            
            # Generate token
            device_token = generate_device_token()
            token_hash = hashlib.sha256(device_token.encode()).hexdigest()
            
            # Create token entry
            new_token = DeviceToken(
                token_hash=token_hash,
                device_id=new_device.id,
                created_at=datetime.utcnow()
            )
            db.add(new_token)
            db.commit()
            
            return RegisterDeviceResponse(
                device_token=device_token,
                quota_remaining=new_device.quota_remaining,
                device_fingerprint=new_device.device_fingerprint
            )
        except IntegrityError:
            db.rollback()
            # Race condition - device was created by another request
            # Retry by querying again
            existing_device = db.query(Device).filter(
                Device.device_fingerprint == device_fingerprint
            ).first()
            
            if existing_device:
                # Generate new token for existing device
                device_token = generate_device_token()
                token_hash = hashlib.sha256(device_token.encode()).hexdigest()
                
                new_token = DeviceToken(
                    token_hash=token_hash,
                    device_id=existing_device.id,
                    created_at=datetime.utcnow()
                )
                db.add(new_token)
                db.commit()
                
                return RegisterDeviceResponse(
                    device_token=device_token,
                    quota_remaining=existing_device.quota_remaining,
                    device_fingerprint=existing_device.device_fingerprint
                )
            else:
                raise HTTPException(status_code=500, detail="Failed to create device")
