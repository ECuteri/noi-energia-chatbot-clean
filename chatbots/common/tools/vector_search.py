import json
import logging
from typing import Callable

from config import HYBRID_SEARCH_CANDIDATES, MAX_SEARCH_RESULTS, RERANK_TOP_N
from services.reranker import rerank_results
from services.supabase_client import supabase_store

logger = logging.getLogger(__name__)

CONTENT_PREVIEW_LENGTH = 500


def _parse_metadata(metadata):
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
    return metadata if isinstance(metadata, dict) else {}


def _format_result(result):
    metadata = _parse_metadata(result.get("metadata", {}))
    metadata_copy = metadata.copy()

    if "file_id" in metadata_copy:
        source_file_id = metadata_copy.pop("file_id")
        metadata_copy["source_file_id"] = source_file_id

    content = result.get("content", "")
    preview = (
        content[:CONTENT_PREVIEW_LENGTH] + "..."
        if len(content) > CONTENT_PREVIEW_LENGTH
        else content
    )

    return {
        "chunk_id": result.get("id"),
        "content": preview,
        "similarity_score": result.get("rerank_score") or result.get("similarity", 0.0),
        "metadata": metadata_copy,
    }


def create_vector_search_tool(table_name: str, chatbot_name: str) -> Callable:

    async def vector_search(query: str, limit: int = None) -> str:
        try:
            logger.info(
                f"{chatbot_name} vector search: query='{query[:100]}...', limit={limit}"
            )

            if not query or not query.strip():
                logger.warning("Empty query provided")
                return "No search query provided."

            final_limit = limit or MAX_SEARCH_RESULTS

            search_results = await supabase_store.hybrid_search(
                query=query.strip(),
                table_name=table_name,
                limit=HYBRID_SEARCH_CANDIDATES,
            )

            if not search_results:
                logger.info(f"{chatbot_name} hybrid search returned no results")
                return "No documents found matching your query."

            reranked_results = await rerank_results(
                query=query.strip(),
                documents=search_results,
                top_n=min(RERANK_TOP_N, final_limit),
            )

            formatted_results = [_format_result(r) for r in reranked_results]

            logger.info(
                f"{chatbot_name} search pipeline: {len(search_results)} candidates -> {len(formatted_results)} reranked results"
            )
            return json.dumps(formatted_results, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(
                f"Error in {chatbot_name} vector search: {str(e)}", exc_info=True
            )
            return f"Error performing search: {str(e)}"

    vector_search.__name__ = "vector_search"
    vector_search.__doc__ = f"""
Search {chatbot_name} documents using hybrid semantic and keyword search with reranking.

This tool uses a multi-stage retrieval pipeline:
1. Hybrid search combining vector similarity with full-text keyword matching
2. Reranking with a cross-encoder model for improved relevance

Parameters:
- query (required): The search query text
- limit (optional): Maximum number of results to return (default: 5)

Returns:
List of document chunks ranked by relevance. Each result contains:
- chunk_id: UNIQUE IDENTIFIER to use with get_file_contents()
- content: Preview of the chunk content (truncated to 500 chars)
- similarity_score: Relevance score from reranking model
- metadata: Additional information (source_file_id is for reference only)

CRITICAL: Always use the 'chunk_id' field from results when calling get_file_contents().
DO NOT use any IDs from the metadata field for document retrieval.

Example usage:
- vector_search(query="energy efficiency")
- vector_search(query="renewable energy sources", limit=5)

After getting results, use get_file_contents(document_id=result['chunk_id']) to retrieve full content.
"""

    return vector_search
