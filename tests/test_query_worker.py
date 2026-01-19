"""Tests for query worker."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from app.db.models import Query, QueryStatus, Ingestion, IngestionStatus
from app.services.query_worker import process_query, _update_failed_status
from app.core.errors import NoContentError, QueryGenerationError


class TestQueryWorker:
    """Test query worker functions."""
    
    def test_process_query_success(self, test_db, test_device, test_ingestion):
        """Test successful query processing."""
        # Create query
        query = Query(
            device_id=test_device.id,
            question="What is this about?",
            status=QueryStatus.PENDING,
            estimated_time_seconds=5,
            created_at=datetime.utcnow()
        )
        test_db.add(query)
        test_db.commit()
        test_db.refresh(query)
        
        # Mock dependencies
        with patch('app.services.query_worker.embed_query') as mock_embed, \
             patch('app.services.query_worker.search_relevant_chunks') as mock_search, \
             patch('app.services.query_worker.assemble_context') as mock_assemble, \
             patch('app.services.query_worker.generate_answer') as mock_answer, \
             patch('app.services.query_worker.log_query_metrics') as mock_metrics:
            
            # Setup mocks
            mock_embed.return_value = [0.1] * 1536
            mock_search.return_value = [
                {
                    'chunk_id': 'chunk1',
                    'ingestion_id': test_ingestion.id,
                    'document': 'Test document',
                    'similarity': 0.9,
                    'distance': 0.1
                }
            ]
            mock_assemble.return_value = ("Test context", 100)
            mock_answer.return_value = ("Test answer", 150)
            mock_metrics.return_value = None
            
            # Process query
            process_query(query.id, "What is this about?", test_device.id, db_session=test_db)
            
            # Verify
            test_db.refresh(query)
            assert query.status == QueryStatus.SUCCESS
            assert query.answer == "Test answer"
            assert query.token_count == 150
            assert query.chunk_count_used == 1
            assert query.error_code is None
            
            # Verify quota was deducted
            test_db.refresh(test_device)
            assert test_device.quota_remaining == 2  # Started with 3, deducted 1
    
    def test_process_query_not_found(self, test_db, test_device):
        """Test processing non-existent query."""
        # Process with invalid ID
        process_query("non-existent-id", "Test question", test_device.id, db_session=test_db)
        
        # Should not raise, just log error
        query = test_db.query(Query).filter(Query.id == "non-existent-id").first()
        assert query is None
    
    def test_process_query_no_ingestion(self, test_db, test_device):
        """Test query with no successful ingestion."""
        # Create query
        query = Query(
            device_id=test_device.id,
            question="What is this about?",
            status=QueryStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(query)
        test_db.commit()
        test_db.refresh(query)
        
        # Process query (no ingestion exists)
        process_query(query.id, "What is this about?", test_device.id, db_session=test_db)
        
        # Verify error status
        test_db.refresh(query)
        assert query.status == QueryStatus.FAILED
        assert query.error_code == "NO_CONTENT"
        assert "No ingested content" in query.error_message
    
    def test_process_query_no_chunks_found(self, test_db, test_device, test_ingestion):
        """Test query with no relevant chunks found."""
        # Create query
        query = Query(
            device_id=test_device.id,
            question="What is this about?",
            status=QueryStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(query)
        test_db.commit()
        test_db.refresh(query)
        
        # Mock dependencies
        with patch('app.services.query_worker.embed_query') as mock_embed, \
             patch('app.services.query_worker.search_relevant_chunks') as mock_search, \
             patch('app.services.query_worker.log_query_metrics') as mock_metrics:
            
            # Setup mocks - no chunks found
            mock_embed.return_value = [0.1] * 1536
            mock_search.side_effect = NoContentError("No chunks found")
            mock_metrics.return_value = None
            
            # Process query
            process_query(query.id, "What is this about?", test_device.id, db_session=test_db)
            
            # Verify refusal response
            test_db.refresh(query)
            assert query.status == QueryStatus.SUCCESS  # Refusal is still SUCCESS
            assert query.error_code == "INSUFFICIENT_RELEVANCE"
            assert "cannot answer" in query.answer.lower()
    
    def test_process_query_embedding_failure(self, test_db, test_device, test_ingestion):
        """Test query with embedding generation failure."""
        # Create query
        query = Query(
            device_id=test_device.id,
            question="What is this about?",
            status=QueryStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(query)
        test_db.commit()
        test_db.refresh(query)
        
        # Mock dependencies
        with patch('app.services.query_worker.embed_query') as mock_embed:
            mock_embed.side_effect = Exception("Embedding error")
            
            # Process query
            process_query(query.id, "What is this about?", test_device.id, db_session=test_db)
            
            # Verify error status
            test_db.refresh(query)
            assert query.status == QueryStatus.FAILED
            assert query.error_code == "UNKNOWN_ERROR"
    
    def test_process_query_llm_failure(self, test_db, test_device, test_ingestion):
        """Test query with LLM generation failure."""
        # Create query
        query = Query(
            device_id=test_device.id,
            question="What is this about?",
            status=QueryStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(query)
        test_db.commit()
        test_db.refresh(query)
        
        # Mock dependencies
        with patch('app.services.query_worker.embed_query') as mock_embed, \
             patch('app.services.query_worker.search_relevant_chunks') as mock_search, \
             patch('app.services.query_worker.assemble_context') as mock_assemble, \
             patch('app.services.query_worker.generate_answer') as mock_answer:
            
            # Setup mocks
            mock_embed.return_value = [0.1] * 1536
            mock_search.return_value = [{'chunk_id': 'chunk1', 'ingestion_id': test_ingestion.id, 'document': 'Test', 'similarity': 0.9}]
            mock_assemble.return_value = ("Test context", 100)
            mock_answer.side_effect = Exception("LLM API error")
            
            # Process query
            process_query(query.id, "What is this about?", test_device.id, db_session=test_db)
            
            # Verify error status
            test_db.refresh(query)
            assert query.status == QueryStatus.FAILED
            assert query.error_code == "UNKNOWN_ERROR"
    
    def test_process_query_quota_deduction(self, test_db, test_device, test_ingestion):
        """Test atomic quota deduction."""
        # Set quota to 1
        test_device.quota_remaining = 1
        test_db.commit()
        test_db.refresh(test_device)
        
        # Create query
        query = Query(
            device_id=test_device.id,
            question="What is this about?",
            status=QueryStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(query)
        test_db.commit()
        test_db.refresh(query)
        
        # Mock dependencies
        with patch('app.services.query_worker.embed_query') as mock_embed, \
             patch('app.services.query_worker.search_relevant_chunks') as mock_search, \
             patch('app.services.query_worker.assemble_context') as mock_assemble, \
             patch('app.services.query_worker.generate_answer') as mock_answer, \
             patch('app.services.query_worker.log_query_metrics') as mock_metrics:
            
            # Setup mocks
            mock_embed.return_value = [0.1] * 1536
            mock_search.return_value = [{'chunk_id': 'chunk1', 'ingestion_id': test_ingestion.id, 'document': 'Test', 'similarity': 0.9}]
            mock_assemble.return_value = ("Test context", 100)
            mock_answer.return_value = ("Test answer", 150)
            mock_metrics.return_value = None
            
            # Process query
            process_query(query.id, "What is this about?", test_device.id, db_session=test_db)
            
            # Verify quota was deducted atomically
            test_db.refresh(test_device)
            assert test_device.quota_remaining == 0
    
    def test_update_failed_status(self, test_db, test_device):
        """Test _update_failed_status helper function."""
        # Create query
        query = Query(
            device_id=test_device.id,
            question="Test question",
            status=QueryStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(query)
        test_db.commit()
        test_db.refresh(query)
        
        # Update failed status
        _update_failed_status(test_db, query.id, "TEST_ERROR", "Test error message")
        
        # Verify
        test_db.refresh(query)
        assert query.status == QueryStatus.FAILED
        assert query.error_code == "TEST_ERROR"
        assert query.error_message == "Test error message"
        assert query.completed_at is not None
    
    def test_update_failed_status_not_found(self, test_db):
        """Test _update_failed_status with non-existent query."""
        # Should not raise, just log error
        _update_failed_status(test_db, "non-existent-id", "TEST_ERROR", "Test error")
        
        # Verify no query was created
        query = test_db.query(Query).filter(Query.id == "non-existent-id").first()
        assert query is None
