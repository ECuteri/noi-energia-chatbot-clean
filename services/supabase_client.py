import logging
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg
from langchain_openai import OpenAIEmbeddings

from config import (
    EMBEDDING_MODEL,
    MAX_SEARCH_RESULTS,
    OPENAI_API_KEY,
    SIMILARITY_THRESHOLD,
    SUPABASE_API_KEY,
    SUPABASE_URL,
)

logger = logging.getLogger(__name__)


class SupabaseVectorStore:

    def __init__(self):
        self.supabase_url = SUPABASE_URL
        self.embedding_model = EMBEDDING_MODEL
        self.max_results = MAX_SEARCH_RESULTS
        self.similarity_threshold = SIMILARITY_THRESHOLD
        self.db_pool = None
        self.supabase = None

        if not self.supabase_url:
            logger.warning(
                "Supabase URL not configured. Vector search will be disabled."
            )
        else:
            logger.info(
                f"Initializing Supabase connection with URL: {self._mask_connection_string(self.supabase_url)}"
            )

        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not found. Embeddings will not work.")
            self.embeddings = None
        else:
            try:
                self.embeddings = OpenAIEmbeddings(
                    model=self.embedding_model, api_key=OPENAI_API_KEY
                )
                logger.info(
                    f"OpenAI embeddings initialized with model: {self.embedding_model}"
                )
                logger.info(
                    f"Vector search similarity threshold: {self.similarity_threshold}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI embeddings: {e}")
                self.embeddings = None

    def _mask_connection_string(self, url: str) -> str:
        if not url:
            return "NOT_SET"
        if "postgresql://" in url or "postgres://" in url:
            parts = url.split("@")
            if len(parts) > 1:
                return f"{parts[0].split('//')[0]}//***:***@{parts[1]}"
        return url

    async def _get_connection(self):
        if self.db_pool is None and self.supabase_url:
            try:
                self.db_pool = await asyncpg.create_pool(
                    self.supabase_url, min_size=1, max_size=10, command_timeout=60
                )
                logger.info("✅ Database connection pool created successfully")
                self.supabase = self.db_pool
                await self._check_pgvector_extension()
            except Exception as e:
                logger.error(f"Failed to create database connection pool: {e}")
                self.db_pool = None
                self.supabase = None
        return self.db_pool

    async def _check_pgvector_extension(self):
        try:
            pool = await self._get_connection()
            if pool:
                async with pool.acquire() as conn:
                    result = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                    )
                    if result:
                        logger.info("✅ pgvector extension is enabled")
                    else:
                        logger.warning(
                            "⚠️  pgvector extension not enabled. Please enable it: CREATE EXTENSION vector;"
                        )
        except Exception as e:
            logger.warning(f"Could not verify pgvector extension: {e}")

    async def close(self):
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Database connection pool closed")

    async def embed_text(self, text: str) -> Optional[List[float]]:
        if not self.embeddings:
            logger.error("Embeddings not initialized")
            return None

        try:
            import asyncio

            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, lambda: self.embeddings.embed_query(text)
            )
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding for text: {e}")
            return None

    async def search_similar(
        self, query: str, table_name: str, limit: int = None
    ) -> List[Dict]:
        pool = await self._get_connection()
        if not pool or not self.embeddings:
            logger.error("Database connection or embeddings not initialized")
            return []

        try:
            query_embedding = await self.embed_text(query)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            limit = limit or self.max_results

            embedding_str = f"[{','.join(map(str, query_embedding))}]"

            async with pool.acquire() as conn:
                sql = f"""
                    SELECT
                        id,
                        content,
                        metadata,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM {table_name}
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                """

                rows = await conn.fetch(sql, embedding_str, limit)

                logger.info(
                    f"Retrieved {len(rows)} rows from {table_name} before filtering"
                )

                if rows:
                    similarity_scores = [row["similarity"] for row in rows]
                    logger.info(
                        f"Similarity scores: min={min(similarity_scores):.3f}, max={max(similarity_scores):.3f}, avg={sum(similarity_scores)/len(similarity_scores):.3f}"
                    )

                results = []
                for row in rows:
                    similarity = float(row["similarity"])
                    if similarity >= self.similarity_threshold:
                        results.append(
                            {
                                "id": str(row["id"]),
                                "content": row["content"] or "",
                                "metadata": row["metadata"] or {},
                                "similarity": similarity,
                            }
                        )
                    else:
                        logger.debug(
                            f"Filtered out document {row['id']} with similarity {similarity:.3f} (threshold: {self.similarity_threshold})"
                        )

                logger.info(
                    f"Found {len(results)} similar documents in {table_name} (threshold: {self.similarity_threshold})"
                )
                return results

        except Exception as e:
            logger.error(f"Error searching similar documents in {table_name}: {e}")
            return []

    async def list_documents(
        self,
        table_name: str,
        metadata_table_name: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        pool = await self._get_connection()
        if not pool:
            logger.error("Database connection not initialized")
            return []

        try:
            async with pool.acquire() as conn:
                sql = f"""
                    SELECT id, title, created_at
                    FROM {metadata_table_name}
                    ORDER BY created_at DESC
                    LIMIT $1 OFFSET $2
                """

                rows = await conn.fetch(sql, limit, offset)

                results = []
                for row in rows:
                    results.append(
                        {
                            "id": str(row["id"]),
                            "title": row["title"] or "Untitled",
                            "created_at": (
                                row["created_at"].isoformat()
                                if row["created_at"]
                                else None
                            ),
                        }
                    )

                logger.info(
                    f"Listed {len(results)} documents from {metadata_table_name}"
                )
                return results

        except Exception as e:
            logger.error(f"Error listing documents from {metadata_table_name}: {e}")
            return []

    async def get_document(
        self, document_id: str, table_name: str, metadata_table_name: str
    ) -> Optional[Dict]:
        pool = await self._get_connection()
        if not pool:
            logger.error("Database connection not initialized")
            return None

        try:
            async with pool.acquire() as conn:
                doc_sql = f"""
                    SELECT id, content, metadata
                    FROM {table_name}
                    WHERE id = $1
                """
                doc_row = await conn.fetchrow(doc_sql, document_id)

                if not doc_row:
                    logger.warning(f"Document {document_id} not found in {table_name}")
                    return None

                metadata_sql = f"""
                    SELECT title, created_at
                    FROM {metadata_table_name}
                    WHERE id = $1
                """
                metadata_row = await conn.fetchrow(metadata_sql, document_id)

                return {
                    "id": str(doc_row["id"]),
                    "content": doc_row["content"] or "",
                    "metadata": doc_row["metadata"] or {},
                    "title": metadata_row["title"] if metadata_row else "Untitled",
                    "created_at": (
                        metadata_row["created_at"].isoformat()
                        if metadata_row and metadata_row["created_at"]
                        else None
                    ),
                }

        except Exception as e:
            logger.error(
                f"Error getting document {document_id} from {table_name}/{metadata_table_name}: {e}"
            )
            return None

    async def save_chat_message(self, session_id: str, role: str, content: str) -> bool:
        pool = await self._get_connection()
        if not pool:
            logger.error("Database connection not initialized")
            return False

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO chat_history (session_id, role, content, created_at)
                    VALUES ($1, $2, $3, $4)
                    """,
                    session_id,
                    role,
                    content,
                    datetime.utcnow(),
                )

                logger.debug(f"Saved chat message for session_id {session_id}")
                return True

        except Exception as e:
            logger.error(f"Error saving chat message for session_id {session_id}: {e}")
            return False

    async def get_chat_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        pool = await self._get_connection()
        if not pool:
            logger.error("Database connection not initialized")
            return []

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT role, content
                    FROM chat_history
                    WHERE session_id = $1
                    ORDER BY created_at ASC
                    LIMIT $2
                    """,
                    session_id,
                    limit,
                )

                return [
                    {"role": row["role"], "content": row["content"]} for row in rows
                ]

        except Exception as e:
            logger.error(
                f"Error retrieving chat history for session_id {session_id}: {e}"
            )
            return []


supabase_store = SupabaseVectorStore()
