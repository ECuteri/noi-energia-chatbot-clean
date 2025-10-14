import json
import logging
from typing import Callable

from services.supabase_client import supabase_store

logger = logging.getLogger(__name__)


def create_list_documents_tool(
    table_name: str, metadata_table_name: str, chatbot_name: str
) -> Callable:

    async def list_documents(limit: int = 50, offset: int = 0) -> str:
        try:
            logger.info(
                f"Listing {chatbot_name} documents: limit={limit}, offset={offset}"
            )

            documents = await supabase_store.list_documents(
                table_name=table_name,
                metadata_table_name=metadata_table_name,
                limit=limit,
                offset=offset,
            )

            if not documents:
                logger.info(f"No {chatbot_name} documents found")
                return "No documents found."

            formatted_docs = []
            for doc in documents:
                formatted_doc = {
                    "id": doc["id"],
                    "title": doc.get("title", "Untitled"),
                    "created_at": doc.get("created_at", ""),
                    "metadata": doc.get("metadata", {}),
                }
                formatted_docs.append(formatted_doc)

            logger.info(f"Found {len(formatted_docs)} {chatbot_name} documents")
            return json.dumps(formatted_docs, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(
                f"Error listing {chatbot_name} documents: {str(e)}", exc_info=True
            )
            return f"Error listing documents: {str(e)}"

    list_documents.__name__ = "list_documents"
    list_documents.__doc__ = f"""
List {chatbot_name} documents from Supabase.

Retrieve a list of {chatbot_name} documents with their metadata. Supports pagination for large result sets.

Parameters:
- limit (optional): Maximum number of documents to return (default: 50)
- offset (optional): Number of documents to skip for pagination (default: 0)

Returns:
List of document objects with id, title, created_at, and metadata fields.

Example usage:
- list_documents()
- list_documents(limit=10)
- list_documents(limit=10, offset=10)
"""

    return list_documents
