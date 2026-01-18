"""Text chunking service."""
from dataclasses import dataclass
from typing import List
import tiktoken
import re

from app.core.config import settings

# Initialize tiktoken encoder
_encoder = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    """Represents a text chunk."""
    text: str
    position: int
    start_char: int
    end_char: int
    token_count: int


def chunk_text(text: str, chunk_size: int = None, overlap: float = None, min_chunk_size: int = None) -> List[Chunk]:
    """
    Chunk text into smaller pieces with overlap.
    
    Args:
        text: Text to chunk
        chunk_size: Target tokens per chunk (default from config)
        overlap: Overlap percentage (default from config)
        min_chunk_size: Minimum tokens per chunk (default from config)
        
    Returns:
        List of Chunk objects
    """
    if chunk_size is None:
        chunk_size = settings.chunk_size
    if overlap is None:
        overlap = settings.chunk_overlap
    if min_chunk_size is None:
        min_chunk_size = getattr(settings, 'min_chunk_size', 50)
    
    if not text or len(text.strip()) == 0:
        return []
    
    # Encode text to tokens
    tokens = _encoder.encode(text)
    
    # If text is too short, return empty (below minimum chunk size)
    if len(tokens) < min_chunk_size:
        return []
    
    if len(tokens) <= chunk_size:
        # Text fits in one chunk and meets minimum size
        return [Chunk(
            text=text,
            position=0,
            start_char=0,
            end_char=len(text),
            token_count=len(tokens)
        )]
    
    chunks = []
    overlap_tokens = int(chunk_size * overlap)
    step_size = chunk_size - overlap_tokens
    
    position = 0
    start_idx = 0
    
    while start_idx < len(tokens):
        end_idx = min(start_idx + chunk_size, len(tokens))
        chunk_tokens = tokens[start_idx:end_idx]
        
        # Decode tokens back to text
        chunk_text_str = _encoder.decode(chunk_tokens)
        
        # Try to find sentence boundaries for better chunking
        if end_idx < len(tokens) and overlap_tokens > 0:
            # Look for sentence endings in the overlap region
            overlap_start = max(0, end_idx - overlap_tokens * 2)
            overlap_tokens_slice = tokens[overlap_start:end_idx]
            overlap_text = _encoder.decode(overlap_tokens_slice)
            
            # Find last sentence boundary
            sentence_endings = re.finditer(r'[.!?]\s+', overlap_text)
            last_sentence_end = None
            for match in sentence_endings:
                last_sentence_end = match.end()
            
            if last_sentence_end:
                # Adjust chunk to end at sentence boundary
                adjusted_tokens = tokens[overlap_start:overlap_start + len(_encoder.encode(overlap_text[:last_sentence_end]))]
                if len(adjusted_tokens) >= chunk_size - overlap_tokens:
                    chunk_tokens = adjusted_tokens
                    chunk_text_str = _encoder.decode(chunk_tokens)
                    end_idx = overlap_start + len(adjusted_tokens)
        
        # Skip chunks that are too small (below minimum)
        if len(chunk_tokens) < min_chunk_size:
            # If this is the last chunk and it's too small, merge with previous
            if chunks and start_idx + chunk_size >= len(tokens):
                # Merge with last chunk
                last_chunk = chunks[-1]
                merged_text = last_chunk.text + " " + chunk_text_str
                merged_tokens = _encoder.encode(merged_text)
                chunks[-1] = Chunk(
                    text=merged_text,
                    position=last_chunk.position,
                    start_char=last_chunk.start_char,
                    end_char=min(last_chunk.end_char + len(chunk_text_str), len(text)),
                    token_count=len(merged_tokens)
                )
            # Otherwise, skip this chunk and continue
            start_idx += step_size
            continue
        
        # Find character positions in original text
        # Approximate by finding the text in original
        start_char = text.find(chunk_text_str[:50]) if len(chunk_text_str) > 50 else 0
        if start_char == -1:
            start_char = position * step_size  # Fallback approximation
        end_char = start_char + len(chunk_text_str)
        
        chunks.append(Chunk(
            text=chunk_text_str,
            position=position,
            start_char=start_char,
            end_char=min(end_char, len(text)),
            token_count=len(chunk_tokens)
        ))
        
        position += 1
        start_idx += step_size
    
    # Filter out any remaining chunks below minimum size
    chunks = [chunk for chunk in chunks if chunk.token_count >= min_chunk_size]
    
    # Re-number positions
    for i, chunk in enumerate(chunks):
        chunk.position = i
    
    return chunks
