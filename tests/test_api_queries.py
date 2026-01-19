"""Integration tests for query endpoints."""
import pytest
from fastapi import status
from app.db.models import Query, QueryStatus


class TestQueryAPI:
    """Test query API endpoints."""
    
    def test_submit_query_requires_auth(self, client):
        """Test that submitting query requires device token."""
        response = client.post(
            "/api/v1/query",
            json={"question": "What is this about?"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_submit_query_invalid_question_too_short(self, client, test_device_token):
        """Test submitting query with too short question."""
        token, _ = test_device_token
        response = client.post(
            "/api/v1/query",
            json={"question": "short"},
            headers={"X-Device-Token": token}
        )
        # FastAPI returns 422 for Pydantic validation errors (min_length=10 in schema)
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]
        data = response.json()
        # Pydantic validation returns different format, so check for either
        if response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
            assert "detail" in data
        else:
            assert data["detail"]["code"] == "INVALID_QUESTION"
    
    def test_submit_query_no_content(self, client, test_device_token):
        """Test submitting query when device has no ingested content."""
        token, _ = test_device_token
        response = client.post(
            "/api/v1/query",
            json={"question": "What is this about?"},
            headers={"X-Device-Token": token}
        )
        # Query is created but will fail in background
        # For now, we just check it's accepted
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]
    
    def test_get_query_status_not_found(self, client, test_device_token):
        """Test getting non-existent query status."""
        token, _ = test_device_token
        response = client.get(
            "/api/v1/queries/non-existent-id",
            headers={"X-Device-Token": token}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_submit_query_with_parameters(self, client, test_device_token):
        """Test submitting query with custom parameters."""
        token, _ = test_device_token
        response = client.post(
            "/api/v1/query",
            json={
                "question": "What is machine learning?",
                "max_chunks": 10,
                "temperature": 0.8
            },
            headers={"X-Device-Token": token}
        )
        # Should accept the request (may fail in background if no content)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]
    
    def test_submit_query_quota_exhausted(self, client, test_db, test_device_token):
        """Test submitting query when quota is exhausted."""
        from app.db.models import Device
        token, device = test_device_token
        
        # Exhaust quota - update in database and refresh
        test_db.query(Device).filter(Device.id == device.id).update({"quota_remaining": 0})
        test_db.commit()
        test_db.refresh(device)
        
        response = client.post(
            "/api/v1/query",
            json={"question": "What is this about?"},
            headers={"X-Device-Token": token}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert data["detail"]["code"] == "QUOTA_EXHAUSTED"
    
    def test_get_query_status_with_chunks(self, client, test_db, test_device_token):
        """Test getting query status with query chunks."""
        from app.db.models import Query, QueryChunk, Ingestion, IngestionStatus, QueryStatus
        from datetime import datetime
        token, device = test_device_token
        
        # Create ingestion
        ingestion = Ingestion(
            device_id=device.id,
            url="https://example.com",
            status=IngestionStatus.SUCCESS,
            created_at=datetime.utcnow()
        )
        test_db.add(ingestion)
        test_db.commit()
        test_db.refresh(ingestion)
        
        # Create query with chunks
        query = Query(
            device_id=device.id,
            question="Test question",
            status=QueryStatus.SUCCESS,
            answer="Test answer",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        test_db.add(query)
        test_db.commit()
        test_db.refresh(query)
        
        # Create query chunk
        chunk = QueryChunk(
            query_id=query.id,
            ingestion_id=ingestion.id,
            chunk_id="chunk-1",
            relevance_score=0.9,
            position=0,  # Required field
            text_snippet="Test snippet"
        )
        test_db.add(chunk)
        test_db.commit()
        
        # Get query status
        response = client.get(
            f"/api/v1/queries/{query.id}",
            headers={"X-Device-Token": token}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["url"] == "https://example.com"
        assert data["sources"][0]["relevance_score"] == 0.9
    
    def test_get_query_status_wrong_device(self, client, test_db, test_device_token):
        """Test getting query from different device is forbidden."""
        from app.db.models import Device, Query, QueryStatus
        from datetime import datetime
        token, device = test_device_token
        
        # Create another device
        other_device = Device(
            device_fingerprint="other_device",
            quota_remaining=3,
            device_model="Other Device",
            os_version="1.0"
        )
        test_db.add(other_device)
        test_db.commit()
        test_db.refresh(other_device)
        
        # Create query for other device
        query = Query(
            device_id=other_device.id,
            question="Other question",
            status=QueryStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(query)
        test_db.commit()
        test_db.refresh(query)
        
        # Try to access with different device token
        response = client.get(
            f"/api/v1/queries/{query.id}",
            headers={"X-Device-Token": token}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert data["detail"]["code"] == "FORBIDDEN"
