"""Integration tests for ingestion endpoints."""
import pytest
from fastapi import status
from app.db.models import Ingestion, IngestionStatus


class TestIngestionAPI:
    """Test ingestion API endpoints."""
    
    def test_scrape_url_requires_auth(self, client):
        """Test that scraping URL requires device token."""
        response = client.post(
            "/api/v1/scrape-url",
            json={"url": "https://example.com"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_scrape_url_invalid_url(self, client, test_device_token):
        """Test scraping with invalid URL."""
        token, _ = test_device_token
        response = client.post(
            "/api/v1/scrape-url",
            json={"url": "not-a-valid-url"},
            headers={"X-Device-Token": token}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "INVALID_URL"
    
    def test_scrape_url_internal_ip(self, client, test_device_token):
        """Test scraping with internal IP is rejected."""
        token, _ = test_device_token
        response = client.post(
            "/api/v1/scrape-url",
            json={"url": "http://127.0.0.1"},
            headers={"X-Device-Token": token}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "INTERNAL_IP_NOT_ALLOWED"
    
    def test_get_ingestion_status_not_found(self, client, test_device_token):
        """Test getting non-existent ingestion status."""
        token, _ = test_device_token
        response = client.get(
            "/api/v1/ingestions/non-existent-id",
            headers={"X-Device-Token": token}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_ingestion_status_wrong_device(self, client, test_db, test_device_token):
        """Test getting ingestion from different device is forbidden."""
        from app.db.models import Device, Ingestion, IngestionStatus
        from datetime import datetime
        
        # Create another device
        other_device = Device(
            device_fingerprint="other_device_fingerprint",
            quota_remaining=3,
            device_model="Other Device",
            os_version="1.0"
        )
        test_db.add(other_device)
        test_db.commit()
        test_db.refresh(other_device)
        
        # Create ingestion for other device
        other_ingestion = Ingestion(
            device_id=other_device.id,
            url="https://example.com",
            status=IngestionStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(other_ingestion)
        test_db.commit()
        test_db.refresh(other_ingestion)
        
        # Try to access with different device token
        token, _ = test_device_token
        response = client.get(
            f"/api/v1/ingestions/{other_ingestion.id}",
            headers={"X-Device-Token": token}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_scrape_url_already_ingested(self, client, test_db, test_device_token):
        """Test scraping URL when device already has ingested content."""
        from app.db.models import Ingestion, IngestionStatus
        from datetime import datetime
        token, device = test_device_token
        
        # Create existing successful ingestion
        existing_ingestion = Ingestion(
            device_id=device.id,
            url="https://example.com",
            status=IngestionStatus.SUCCESS,
            created_at=datetime.utcnow()
        )
        test_db.add(existing_ingestion)
        test_db.commit()
        
        # Try to ingest another URL
        response = client.post(
            "/api/v1/scrape-url",
            json={"url": "https://another-example.com"},
            headers={"X-Device-Token": token}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "URL_ALREADY_INGESTED"
        assert data["detail"]["details"]["existing_url"] == "https://example.com"
