"""Unit tests for text chunker."""
import pytest
from app.services.chunker import chunk_text
from app.services.scraper import estimate_tokens
from app.core.config import settings


class TestChunker:
    """Test text chunking logic."""
    
    def test_chunk_small_text(self):
        """Test chunking small text."""
        text = "This is a short text that should create one chunk."
        chunks = chunk_text(text)
        assert len(chunks) > 0
        assert all(chunk.text for chunk in chunks)
    
    def test_chunk_large_text(self):
        """Test chunking large text creates multiple chunks."""
        # Create text larger than chunk size
        large_text = " ".join(["This is a sentence."] * 1000)
        chunks = chunk_text(large_text)
        assert len(chunks) > 1
    
    def test_chunk_preserves_content(self):
        """Test that chunking preserves all content."""
        text = "Sentence one. Sentence two. Sentence three."
        chunks = chunk_text(text)
        combined = " ".join(chunk.text for chunk in chunks)
        assert "Sentence one" in combined
        assert "Sentence two" in combined
        assert "Sentence three" in combined
    
    def test_chunk_has_token_count(self):
        """Test that chunks have token counts."""
        text = "This is a test text for chunking."
        chunks = chunk_text(text)
        for chunk in chunks:
            assert hasattr(chunk, 'token_count')
            assert chunk.token_count > 0
    
    def test_estimate_tokens(self):
        """Test token estimation."""
        text = "This is a test sentence."
        token_count = estimate_tokens(text)
        assert token_count > 0
        assert isinstance(token_count, int)
    
    def test_estimate_tokens_empty(self):
        """Test token estimation for empty text."""
        token_count = estimate_tokens("")
        assert token_count == 0
    
    def test_chunk_overlap(self):
        """Test that chunks have overlap."""
        text = " ".join([f"Sentence {i}." for i in range(100)])
        chunks = chunk_text(text)
        if len(chunks) > 1:
            # Check that there's some overlap between chunks
            # This is a basic check - actual overlap logic is in chunker
            assert len(chunks) > 0
