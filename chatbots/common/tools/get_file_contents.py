import logging
from typing import Callable

from services.supabase_client import supabase_store

logger = logging.getLogger(__name__)


def create_get_file_contents_tool(
    table_name: str, metadata_table_name: str, chatbot_name: str
) -> Callable:

    async def get_file_contents(document_id: str) -> str:
        try:
            logger.info(f"Retrieving {chatbot_name} document content: {document_id}")

            if not document_id:
                logger.warning("Document ID is required")
                return "Document ID is required."

            if "-" not in document_id and len(document_id) > 20:
                logger.warning(
                    f"Invalid document ID format detected (possible Google Drive ID): {document_id}"
                )
                return (
                    f"ERROR: Invalid document ID format '{document_id}'. "
                    "This appears to be a Google Drive file ID from metadata, which cannot be used for retrieval. "
                    "You MUST use the 'chunk_id' field from vector_search results instead. "
                    "The chunk_id is a UUID format (e.g., '0035349d-2e09-45f4-9385-9185000ab193'). "
                    "Please perform vector_search again and use the 'chunk_id' from the results."
                )

            document = await supabase_store.get_document(
                document_id=document_id,
                table_name=table_name,
                metadata_table_name=metadata_table_name,
            )

            if not document:
                logger.warning(f"{chatbot_name} document not found: {document_id}")
                return f"Document with ID '{document_id}' not found."

            content = document.get("content", "")

            if not content:
                logger.warning(
                    f"{chatbot_name} document found but has no content: {document_id}"
                )
                return "Document found but has no content."

            logger.info(
                f"Successfully retrieved {chatbot_name} document: {document_id} ({len(content)} characters)"
            )
            return content

        except Exception as e:
            logger.error(
                f"Error retrieving {chatbot_name} document {document_id}: {str(e)}",
                exc_info=True,
            )
            return f"Error retrieving document: {str(e)}"

    get_file_contents.__name__ = "get_file_contents"
    get_file_contents.__doc__ = f"""
Retrieve the full contents of a {chatbot_name} document chunk by its chunk ID.

Get the complete text content of a {chatbot_name} document chunk. Use this to access full document content.

Parameters:
- document_id (required): The chunk_id from vector_search results (UUID format, e.g., '0035349d-2e09-45f4-9385-9185000ab193')

CRITICAL: You MUST use the 'chunk_id' field from vector_search results, NOT any IDs from metadata.
DO NOT use Google Drive file IDs or source_file_id values - they will fail.

Returns:
The full content of the document chunk as a string. Returns error message if document not found.

Example usage:
- First get results: results = vector_search(query="energy efficiency")
- Then retrieve content: get_file_contents(document_id=results[0]['chunk_id'])

WRONG: get_file_contents(document_id=results[0]['metadata']['source_file_id'])  # Will fail!
RIGHT: get_file_contents(document_id=results[0]['chunk_id'])  # Correct!
"""

    return get_file_contents
