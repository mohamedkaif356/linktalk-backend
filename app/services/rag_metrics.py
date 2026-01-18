"""RAG metrics and instrumentation service."""
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def log_query_metrics(
    query_id: str,
    question: str,
    chunks_retrieved: int,
    chunks_after_threshold: int,
    similarity_scores: List[float],
    token_count: int,
    answer_length: int,
    refused: bool = False,
    error_code: Optional[str] = None
) -> Dict:
    """
    Log comprehensive RAG metrics for analysis.
    
    Args:
        query_id: Query ID
        question: User's question
        chunks_retrieved: Number of chunks retrieved before threshold filtering
        chunks_after_threshold: Number of chunks after similarity threshold filtering
        similarity_scores: List of similarity scores for retrieved chunks
        token_count: Total token count for the query
        answer_length: Length of generated answer in characters
        refused: Whether the query was refused due to insufficient relevance
        error_code: Error code if query failed
        
    Returns:
        Dictionary of metrics
    """
    avg_similarity = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0
    min_similarity = min(similarity_scores) if similarity_scores else 0.0
    max_similarity = max(similarity_scores) if similarity_scores else 0.0
    
    # Estimate cost (GPT-4o-mini pricing: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens)
    # Rough estimate: assume 80% input, 20% output
    input_tokens_estimate = int(token_count * 0.8)
    output_tokens_estimate = int(token_count * 0.2)
    estimated_cost_usd = (input_tokens_estimate / 1_000_000 * 0.15) + (output_tokens_estimate / 1_000_000 * 0.60)
    
    metrics = {
        "query_id": query_id,
        "timestamp": datetime.utcnow().isoformat(),
        "question_length": len(question),
        "chunks_retrieved": chunks_retrieved,
        "chunks_after_threshold": chunks_after_threshold,
        "similarity_stats": {
            "avg": round(avg_similarity, 4),
            "min": round(min_similarity, 4),
            "max": round(max_similarity, 4),
            "count": len(similarity_scores)
        },
        "token_count": token_count,
        "answer_length": answer_length,
        "refused": refused,
        "error_code": error_code,
        "estimated_cost_usd": round(estimated_cost_usd, 6)
    }
    
    logger.info(f"RAG_METRICS: {metrics}")
    return metrics
