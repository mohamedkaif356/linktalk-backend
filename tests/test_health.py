"""Integration tests for health check endpoint."""
import pytest
from fastapi import status


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "vector_db" in data
        assert "openai" in data
    
    def test_health_check_structure(self, client):
        """Test health check response structure."""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Check database status structure
        assert isinstance(data["database"], dict)
        assert "status" in data["database"]
        
        # Check vector_db status structure
        assert isinstance(data["vector_db"], dict)
        assert "status" in data["vector_db"]
        
        # Check openai status structure
        assert isinstance(data["openai"], dict)
        assert "status" in data["openai"]
