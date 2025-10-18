import json
import logging
from typing import Callable

from config import MAX_SEARCH_RESULTS
from services.supabase_client import supabase_store

logger = logging.getLogger(__name__)


def create_vector_search_tool(table_name: str, chatbot_name: str) -> Callable:

    async def vector_search(query: str, limit: int = None) -> str:
        try:
            logger.info(
                f"{chatbot_name} vector search: query='{query[:100]}...', limit={limit}"
            )

            if not query or not query.strip():
                logger.warning("Empty query provided")
                return "No search query provided."

            search_results = await supabase_store.search_similar(
                query=query.strip(),
                table_name=table_name,
                limit=limit or MAX_SEARCH_RESULTS,
            )

            if not search_results:
                logger.info(f"{chatbot_name} vector search returned no results")
                return "No documents found matching your query."

            formatted_results = []
            for result in search_results:
                metadata = result.get("metadata", {})

                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"Could not parse metadata as JSON: {metadata}")
                        metadata = {}

                if not isinstance(metadata, dict):
                    metadata = {}

                metadata_copy = metadata.copy()
                if "file_id" in metadata_copy:
                    source_file_id = metadata_copy.pop("file_id")
                    metadata_copy["source_file_id"] = source_file_id

                formatted_result = {
                    "chunk_id": result.get("id"),
                    "content": (
                        result.get("content", "")[:300] + "..."
                        if len(result.get("content", "")) > 300
                        else result.get("content", "")
                    ),
                    "similarity_score": result.get("similarity", 0.0),
                    "metadata": metadata_copy,
                }
                formatted_results.append(formatted_result)

            logger.info(
                f"{chatbot_name} vector search returned {len(formatted_results)} results"
            )
            return json.dumps(formatted_results, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(
                f"Error in {chatbot_name} vector search: {str(e)}", exc_info=True
            )
            return f"Error performing search: {str(e)}"

    vector_search.__name__ = "vector_search"
    vector_search.__doc__ = f"""
Search {chatbot_name} documents using semantic vector similarity.

This tool searches through {chatbot_name} documents using vector embeddings to find semantically similar content.

Parameters:
- query (required): The search query text
- limit (optional): Maximum number of results to return (default: 10)

Returns:
List of document chunks with similarity scores. Each result contains:
- chunk_id: UNIQUE IDENTIFIER to use with get_file_contents() - this is the ONLY valid ID for retrieval
- content: Preview of the chunk content (truncated to 500 chars)
- similarity_score: Relevance score from 0.0 to 1.0
- metadata: Additional information (source_file_id is for reference only, DO NOT use it for retrieval)

CRITICAL: Always use the 'chunk_id' field from results when calling get_file_contents().
DO NOT use any IDs from the metadata field for document retrieval.

Example usage:
- vector_search(query="energy efficiency")
- vector_search(query="renewable energy sources", limit=5)

After getting results, use get_file_contents(document_id=result['chunk_id']) to retrieve full content.
"""

    return vector_search
