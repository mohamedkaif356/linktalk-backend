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
