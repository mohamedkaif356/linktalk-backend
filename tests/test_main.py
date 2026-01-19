"""Tests for main application."""
import pytest
from unittest.mock import PropertyMock, patch
from fastapi import status
from fastapi.testclient import TestClient
from app.main import app


class TestMainApp:
    """Test main application endpoints and error handlers."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "RAG Backend API"
        assert data["version"] == "1.0.0"
    
    def test_health_check_degraded_vector_db(self, client, monkeypatch):
        """Test health check when vector DB fails."""
        # Mock vector DB to raise exception
        def mock_get_collection():
            raise Exception("Vector DB connection failed")
        
        monkeypatch.setattr("app.services.vector_db.get_collection", mock_get_collection)
        
        response = client.get("/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] in ["degraded", "unhealthy"]
        assert data["vector_db"]["status"] == "error"
    
    def test_health_check_openai_not_configured(self, client, monkeypatch):
        """Test health check when OpenAI is not configured."""
        # Mock settings to have invalid API key
        monkeypatch.setattr("app.core.config.settings.openai_api_key", "short")
        
        response = client.get("/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["openai"]["status"] == "not_configured"
    
    def test_health_check_openai_error(self, client):
        """Test health check when OpenAI check raises exception."""
        # Mock settings.openai_api_key to raise exception when accessed
        with patch('app.main.settings') as mock_settings:
            # Make openai_api_key property raise exception
            type(mock_settings).openai_api_key = PropertyMock(side_effect=Exception("Settings error"))
            
            response = client.get("/health")
            # Should handle gracefully
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
            data = response.json()
            assert data["openai"]["status"] == "error"
    
    def test_validation_error_handler_missing_field(self, client):
        """Test validation error handler for missing field."""
        response = client.post(
            "/api/v1/register-device",
            json={}  # Missing all fields
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "MISSING_FIELD"
    
    def test_validation_error_handler_other_error(self, client):
        """Test validation error handler for other validation errors."""
        response = client.post(
            "/api/v1/query",
            json={"question": "x" * 501}  # Too long
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
