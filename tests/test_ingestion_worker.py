"""Tests for ingestion worker."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from app.db.models import Ingestion, IngestionStatus
from app.services.ingestion_worker import process_ingestion, _update_failed_status
from app.core.errors import ScrapingError
from app.services.chunker import Chunk


class TestIngestionWorker:
    """Test ingestion worker functions."""
    
    def test_process_ingestion_success(self, test_db, test_device):
        """Test successful ingestion processing."""
        # Create ingestion
        ingestion = Ingestion(
            device_id=test_device.id,
            url="https://example.com",
            status=IngestionStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(ingestion)
        test_db.commit()
        test_db.refresh(ingestion)
        
        # Mock dependencies
        with patch('app.services.ingestion_worker.fetch_html') as mock_fetch, \
             patch('app.services.ingestion_worker.extract_readable_content') as mock_extract, \
             patch('app.services.ingestion_worker.estimate_tokens') as mock_estimate, \
             patch('app.services.ingestion_worker.chunk_text') as mock_chunk, \
             patch('app.services.ingestion_worker.generate_embeddings') as mock_embed, \
             patch('app.services.ingestion_worker.store_chunks') as mock_store:
            
            # Setup mocks
            mock_fetch.return_value = "<html><body>Test content</body></html>"
            mock_extract.return_value = "Test content extracted from HTML"
            mock_estimate.return_value = 100  # Within limit
            mock_chunk.return_value = [
                Chunk(text="Chunk 1", position=0, start_char=0, end_char=50, token_count=50),
                Chunk(text="Chunk 2", position=1, start_char=50, end_char=100, token_count=50)
            ]
            mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]
            mock_store.return_value = None
            
            # Process ingestion
            process_ingestion(ingestion.id, "https://example.com", test_device.id, db_session=test_db)
            
            # Verify
            test_db.refresh(ingestion)
            assert ingestion.status == IngestionStatus.SUCCESS
            assert ingestion.chunk_count == 2
            assert ingestion.token_count == 100
            assert ingestion.error_code is None
            
            # Verify mocks were called
            mock_fetch.assert_called_once_with("https://example.com")
            mock_extract.assert_called_once()
            mock_chunk.assert_called_once()
            mock_embed.assert_called_once()
            mock_store.assert_called_once()
    
    def test_process_ingestion_not_found(self, test_db, test_device):
        """Test processing non-existent ingestion."""
        # Process with invalid ID
        process_ingestion("non-existent-id", "https://example.com", test_device.id, db_session=test_db)
        
        # Should not raise, just log error
        # Verify no ingestion was created
        ingestion = test_db.query(Ingestion).filter(Ingestion.id == "non-existent-id").first()
        assert ingestion is None
    
    def test_process_ingestion_scraping_error(self, test_db, test_device):
        """Test ingestion with scraping error."""
        # Create ingestion
        ingestion = Ingestion(
            device_id=test_device.id,
            url="https://example.com",
            status=IngestionStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(ingestion)
        test_db.commit()
        test_db.refresh(ingestion)
        
        # Mock fetch_html to raise ScrapingError
        with patch('app.services.ingestion_worker.fetch_html') as mock_fetch:
            mock_fetch.side_effect = ScrapingError("NETWORK_ERROR", "Network connection failed")
            
            # Process ingestion
            process_ingestion(ingestion.id, "https://example.com", test_device.id, db_session=test_db)
            
            # Verify
            test_db.refresh(ingestion)
            assert ingestion.status == IngestionStatus.FAILED
            assert ingestion.error_code == "NETWORK_ERROR"
            assert "Network connection failed" in ingestion.error_message
    
    def test_process_ingestion_truncation(self, test_db, test_device):
        """Test ingestion with text truncation."""
        # Create ingestion
        ingestion = Ingestion(
            device_id=test_device.id,
            url="https://example.com",
            status=IngestionStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(ingestion)
        test_db.commit()
        test_db.refresh(ingestion)
        
        # Mock dependencies with large text
        with patch('app.services.ingestion_worker.fetch_html') as mock_fetch, \
             patch('app.services.ingestion_worker.extract_readable_content') as mock_extract, \
             patch('app.services.ingestion_worker.estimate_tokens') as mock_estimate, \
             patch('app.services.ingestion_worker.truncate_text') as mock_truncate, \
             patch('app.services.ingestion_worker.chunk_text') as mock_chunk, \
             patch('app.services.ingestion_worker.generate_embeddings') as mock_embed, \
             patch('app.services.ingestion_worker.store_chunks') as mock_store:
            
            # Setup mocks - text exceeds max_tokens
            mock_fetch.return_value = "<html><body>Large content</body></html>"
            mock_extract.return_value = "Large text content"
            mock_estimate.side_effect = [200000, 150000]  # First exceeds, then after truncation
            mock_truncate.return_value = "Truncated text content"
            mock_chunk.return_value = [Chunk(text="Chunk 1", position=0, start_char=0, end_char=50, token_count=50)]
            mock_embed.return_value = [[0.1] * 1536]
            mock_store.return_value = None
            
            # Process ingestion
            process_ingestion(ingestion.id, "https://example.com", test_device.id, db_session=test_db)
            
            # Verify truncation was called
            mock_truncate.assert_called_once()
            test_db.refresh(ingestion)
            assert ingestion.status == IngestionStatus.SUCCESS
    
    def test_process_ingestion_empty_chunks(self, test_db, test_device):
        """Test ingestion with no chunks generated."""
        # Create ingestion
        ingestion = Ingestion(
            device_id=test_device.id,
            url="https://example.com",
            status=IngestionStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(ingestion)
        test_db.commit()
        test_db.refresh(ingestion)
        
        # Mock dependencies with empty chunks
        with patch('app.services.ingestion_worker.fetch_html') as mock_fetch, \
             patch('app.services.ingestion_worker.extract_readable_content') as mock_extract, \
             patch('app.services.ingestion_worker.estimate_tokens') as mock_estimate, \
             patch('app.services.ingestion_worker.chunk_text') as mock_chunk:
            
            # Setup mocks - empty chunks
            mock_fetch.return_value = "<html><body></body></html>"
            mock_extract.return_value = ""
            mock_estimate.return_value = 10
            mock_chunk.return_value = []  # Empty chunks
            
            # Process ingestion
            process_ingestion(ingestion.id, "https://example.com", test_device.id, db_session=test_db)
            
            # Verify error status
            test_db.refresh(ingestion)
            assert ingestion.status == IngestionStatus.FAILED
            assert ingestion.error_code == "NO_CONTENT"
    
    def test_process_ingestion_embedding_failure(self, test_db, test_device):
        """Test ingestion with embedding generation failure."""
        # Create ingestion
        ingestion = Ingestion(
            device_id=test_device.id,
            url="https://example.com",
            status=IngestionStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(ingestion)
        test_db.commit()
        test_db.refresh(ingestion)
        
        # Mock dependencies
        with patch('app.services.ingestion_worker.fetch_html') as mock_fetch, \
             patch('app.services.ingestion_worker.extract_readable_content') as mock_extract, \
             patch('app.services.ingestion_worker.estimate_tokens') as mock_estimate, \
             patch('app.services.ingestion_worker.chunk_text') as mock_chunk, \
             patch('app.services.ingestion_worker.generate_embeddings') as mock_embed:
            
            # Setup mocks
            mock_fetch.return_value = "<html><body>Test</body></html>"
            mock_extract.return_value = "Test content"
            mock_estimate.return_value = 100
            mock_chunk.return_value = [Chunk(text="Chunk 1", position=0, start_char=0, end_char=50, token_count=50)]
            mock_embed.side_effect = Exception("OpenAI API error")
            
            # Process ingestion
            process_ingestion(ingestion.id, "https://example.com", test_device.id, db_session=test_db)
            
            # Verify error status
            test_db.refresh(ingestion)
            assert ingestion.status == IngestionStatus.FAILED
            assert ingestion.error_code == "UNKNOWN_ERROR"
    
    def test_process_ingestion_with_db_session(self, test_db, test_device):
        """Test ingestion with provided database session."""
        # Create ingestion
        ingestion = Ingestion(
            device_id=test_device.id,
            url="https://example.com",
            status=IngestionStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(ingestion)
        test_db.commit()
        test_db.refresh(ingestion)
        
        # Mock dependencies
        with patch('app.services.ingestion_worker.fetch_html') as mock_fetch, \
             patch('app.services.ingestion_worker.extract_readable_content') as mock_extract, \
             patch('app.services.ingestion_worker.estimate_tokens') as mock_estimate, \
             patch('app.services.ingestion_worker.chunk_text') as mock_chunk, \
             patch('app.services.ingestion_worker.generate_embeddings') as mock_embed, \
             patch('app.services.ingestion_worker.store_chunks') as mock_store:
            
            # Setup mocks
            mock_fetch.return_value = "<html><body>Test</body></html>"
            mock_extract.return_value = "Test content"
            mock_estimate.return_value = 100
            mock_chunk.return_value = [Chunk(text="Chunk 1", position=0, start_char=0, end_char=50, token_count=50)]
            mock_embed.return_value = [[0.1] * 1536]
            mock_store.return_value = None
            
            # Process with provided session
            process_ingestion(ingestion.id, "https://example.com", test_device.id, db_session=test_db)
            
            # Verify session was used (session should still be active and usable)
            # When db_session is provided, it's not closed by process_ingestion
            test_db.refresh(ingestion)
            assert ingestion.status == IngestionStatus.SUCCESS
    
    def test_update_failed_status(self, test_db, test_device):
        """Test _update_failed_status helper function."""
        # Create ingestion
        ingestion = Ingestion(
            device_id=test_device.id,
            url="https://example.com",
            status=IngestionStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(ingestion)
        test_db.commit()
        test_db.refresh(ingestion)
        
        # Update failed status
        _update_failed_status(test_db, ingestion.id, "TEST_ERROR", "Test error message")
        
        # Verify
        test_db.refresh(ingestion)
        assert ingestion.status == IngestionStatus.FAILED
        assert ingestion.error_code == "TEST_ERROR"
        assert ingestion.error_message == "Test error message"
        assert ingestion.completed_at is not None
    
    def test_update_failed_status_not_found(self, test_db):
        """Test _update_failed_status with non-existent ingestion."""
        # Should not raise, just log error
        _update_failed_status(test_db, "non-existent-id", "TEST_ERROR", "Test error")
        
        # Verify no ingestion was created
        ingestion = test_db.query(Ingestion).filter(Ingestion.id == "non-existent-id").first()
        assert ingestion is None
