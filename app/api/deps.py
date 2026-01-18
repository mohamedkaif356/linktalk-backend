from fastapi import Header, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.db.models import Device, DeviceToken
from app.core.errors import UnauthorizedError
import hashlib


def get_current_device(
    x_device_token: Optional[str] = Header(None, alias="X-Device-Token"),
    db: Session = Depends(get_db)
) -> Device:
    """
    FastAPI dependency to validate device token and return device context.
    
    Used by all protected endpoints to authenticate requests.
    
    Raises:
        UnauthorizedError: If token is missing, invalid, revoked, or expired
    """
    if not x_device_token:
        raise UnauthorizedError("Missing X-Device-Token header")
    
    # Hash the token to look it up
    token_hash = hashlib.sha256(x_device_token.encode()).hexdigest()
    
    # Look up token in database
    device_token = db.query(DeviceToken).filter(
        DeviceToken.token_hash == token_hash
    ).first()
    
    if not device_token:
        raise UnauthorizedError("Invalid device token")
    
    # Check if token is active
    if not device_token.is_active:
        raise UnauthorizedError("Device token has been revoked or expired")
    
    # Get the associated device
    device = db.query(Device).filter(Device.id == device_token.device_id).first()
    
    if not device:
        raise UnauthorizedError("Device not found")
    
    # Update last_seen_at
    from datetime import datetime
    device.last_seen_at = datetime.utcnow()
    db.commit()
    
    return device
