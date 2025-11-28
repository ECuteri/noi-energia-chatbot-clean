import logging
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg
from langchain_openai import OpenAIEmbeddings

from config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    HYBRID_SEARCH_CANDIDATES,
    HYBRID_SEARCH_ENABLED,
    MAX_SEARCH_RESULTS,
    OPENROUTER_API_KEY,
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
        self._detected_dimensions = {}

        if not self.supabase_url:
            logger.warning(
                "Supabase URL not configured. Vector search will be disabled."
            )
        else:
            logger.info(
                f"Initializing Supabase connection with URL: {self._mask_connection_string(self.supabase_url)}"
            )

        if not OPENROUTER_API_KEY:
            logger.error("OpenRouter API key not found. Embeddings will not work.")
            self.embeddings = None
        else:
            try:
                embedding_kwargs = {
                    "model": self.embedding_model,
                    "api_key": OPENROUTER_API_KEY,
                    "base_url": "https://openrouter.ai/api/v1",
                    "default_headers": {
                        "HTTP-Referer": "https://noienergia.com",
                        "X-Title": "NOI Energia Chatbot",
                    },
                }

                if (
                    "embedding-3-large" in self.embedding_model.lower()
                    or "embedding-3-small" in self.embedding_model.lower()
                ):
                    embedding_kwargs["dimensions"] = EMBEDDING_DIMENSIONS
                    logger.info(
                        f"Setting embedding dimensions to {EMBEDDING_DIMENSIONS} for model {self.embedding_model}"
                    )

                self.embeddings = OpenAIEmbeddings(**embedding_kwargs)
                logger.info(
                    f"OpenRouter embeddings initialized with model: {self.embedding_model} (configured for {EMBEDDING_DIMENSIONS} dimensions)"
                )
                logger.info(
                    f"Vector search similarity threshold: {self.similarity_threshold}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize OpenRouter embeddings: {e}")
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
                    self.supabase_url,
                    min_size=1,
                    max_size=10,
                    command_timeout=60,
                    statement_cache_size=0,
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

    async def _detect_stored_vector_dimensions(self, table_name: str) -> Optional[int]:
        if table_name in self._detected_dimensions:
            return self._detected_dimensions[table_name]

        pool = await self._get_connection()
        if not pool:
            return None

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""
                    SELECT embedding::text as embedding_str
                    FROM {table_name}
                    WHERE embedding IS NOT NULL
                    LIMIT 1
                    """
                )

                if row and row["embedding_str"]:
                    vec_str = row["embedding_str"]
                    if vec_str.startswith("[") and vec_str.endswith("]"):
                        dim = len(vec_str.strip("[]").split(","))
                        self._detected_dimensions[table_name] = dim
                        logger.info(
                            f"Detected stored vector dimensions for {table_name}: {dim}"
                        )
                        return dim
                    else:
                        parts = vec_str.split(",")
                        if len(parts) > 1:
                            dim = len(parts)
                            self._detected_dimensions[table_name] = dim
                            logger.info(
                                f"Detected stored vector dimensions for {table_name}: {dim}"
                            )
                            return dim
                else:
                    logger.warning(
                        f"No vectors found in {table_name} to detect dimensions"
                    )
                    return None
        except Exception as e:
            logger.warning(f"Could not detect vector dimensions for {table_name}: {e}")
            return None

    async def close(self):
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Database connection pool closed")

    async def embed_text(
        self, text: str, target_dimensions: Optional[int] = None
    ) -> Optional[List[float]]:
        if not self.embeddings:
            logger.error("Embeddings not initialized")
            return None

        try:
            import asyncio

            embedding_kwargs_override = {}
            if target_dimensions and target_dimensions != EMBEDDING_DIMENSIONS:
                if (
                    "embedding-3-large" in self.embedding_model.lower()
                    or "embedding-3-small" in self.embedding_model.lower()
                ):
                    embedding_kwargs_override["dimensions"] = target_dimensions
                    logger.info(
                        f"Overriding embedding dimensions to {target_dimensions} "
                        f"to match stored vectors (config: {EMBEDDING_DIMENSIONS})"
                    )

            if embedding_kwargs_override:
                original_kwargs = {
                    "model": self.embedding_model,
                    "api_key": OPENROUTER_API_KEY,
                    "base_url": "https://openrouter.ai/api/v1",
                    "default_headers": {
                        "HTTP-Referer": "https://noienergia.com",
                        "X-Title": "NOI Energia Chatbot",
                    },
                    **embedding_kwargs_override,
                }
                temp_embeddings = OpenAIEmbeddings(**original_kwargs)
                loop = asyncio.get_event_loop()
                embedding = await loop.run_in_executor(
                    None, lambda: temp_embeddings.embed_query(text)
                )
            else:
                loop = asyncio.get_event_loop()
                embedding = await loop.run_in_executor(
                    None, lambda: self.embeddings.embed_query(text)
                )

            if embedding:
                actual_dim = len(embedding)
                if target_dimensions and actual_dim != target_dimensions:
                    logger.warning(
                        f"Embedding dimension mismatch: generated {actual_dim} dimensions, "
                        f"expected {target_dimensions}."
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
            stored_dim = await self._detect_stored_vector_dimensions(table_name)
            query_embedding = await self.embed_text(query, target_dimensions=stored_dim)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            limit = limit or self.max_results
            actual_dim = len(query_embedding)

            embedding_str = f"[{','.join(map(str, query_embedding))}]"

            async with pool.acquire() as conn:
                try:
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
                except Exception as dim_error:
                    if "different vector dimensions" in str(dim_error):
                        logger.error(
                            f"Vector dimension mismatch: Query embedding has {actual_dim} dimensions. "
                            f"Stored vectors have different dimensions. "
                            f"Please check your EMBEDDING_DIMENSIONS setting (currently {EMBEDDING_DIMENSIONS}) "
                            f"matches the dimensions of vectors stored in {table_name}."
                        )
                        logger.error(f"Full error: {dim_error}")

                        stored_dim = await self._detect_stored_vector_dimensions(
                            table_name
                        )
                        if stored_dim and stored_dim != actual_dim:
                            logger.info(
                                f"Retrying with detected stored dimensions: {stored_dim}"
                            )
                            query_embedding = await self.embed_text(
                                query, target_dimensions=stored_dim
                            )
                            if query_embedding:
                                embedding_str = (
                                    f"[{','.join(map(str, query_embedding))}]"
                                )
                                rows = await conn.fetch(sql, embedding_str, limit)
                            else:
                                raise
                        else:
                            raise
                    else:
                        raise

                logger.info(
                    f"Retrieved {len(rows)} rows from {table_name} before filtering"
                )

                if rows:
                    similarity_scores = [row["similarity"] for row in rows]
                    max_score = max(similarity_scores)
                    min_score = min(similarity_scores)
                    avg_score = sum(similarity_scores) / len(similarity_scores)
                    logger.info(
                        f"Similarity scores: min={min_score:.3f}, max={max_score:.3f}, avg={avg_score:.3f}, threshold={self.similarity_threshold}"
                    )
                    if max_score < self.similarity_threshold:
                        logger.warning(
                            f"All {len(rows)} results below threshold {self.similarity_threshold}. "
                            f"Highest score: {max_score:.3f}. Consider lowering SIMILARITY_THRESHOLD."
                        )

                results = []
                filtered_count = 0
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
                        filtered_count += 1
                        logger.debug(
                            f"Filtered out document {row['id']} with similarity {similarity:.3f} (threshold: {self.similarity_threshold})"
                        )

                if filtered_count > 0 and not results:
                    logger.warning(
                        f"All {len(rows)} results filtered out by threshold {self.similarity_threshold}. "
                        f"Returning top {limit or self.max_results} results anyway."
                    )
                    results = [
                        {
                            "id": str(row["id"]),
                            "content": row["content"] or "",
                            "metadata": row["metadata"] or {},
                            "similarity": float(row["similarity"]),
                        }
                        for row in rows[: limit or self.max_results]
                    ]

                logger.info(
                    f"Found {len(results)} similar documents in {table_name} (threshold: {self.similarity_threshold})"
                )
                return results

        except Exception as e:
            logger.error(f"Error searching similar documents in {table_name}: {e}")
            return []

    async def _full_text_search(
        self, query: str, table_name: str, limit: int, conn
    ) -> List[Dict]:
        try:
            fts_sql = f"""
                SELECT
                    id,
                    content,
                    metadata,
                    ts_rank(content_tsv, plainto_tsquery('italian', $1)) as rank
                FROM {table_name}
                WHERE content_tsv @@ plainto_tsquery('italian', $1)
                ORDER BY rank DESC
                LIMIT $2
            """
            rows = await conn.fetch(fts_sql, query, limit)
            return [
                {
                    "id": str(row["id"]),
                    "content": row["content"] or "",
                    "metadata": row["metadata"] or {},
                    "rank": float(row["rank"]),
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Full-text search failed (column may not exist): {e}")
            return []

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict],
        fts_results: List[Dict],
        k: int = 60,
    ) -> List[Dict]:
        scores = {}
        doc_data = {}

        for rank, doc in enumerate(vector_results):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            doc_data[doc_id] = doc

        for rank, doc in enumerate(fts_results):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            if doc_id not in doc_data:
                doc_data[doc_id] = doc

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        results = []
        for doc_id in sorted_ids:
            doc = doc_data[doc_id]
            doc["rrf_score"] = scores[doc_id]
            results.append(doc)

        return results

    async def hybrid_search(
        self, query: str, table_name: str, limit: int = None
    ) -> List[Dict]:
        if not HYBRID_SEARCH_ENABLED:
            return await self.search_similar(query, table_name, limit)

        pool = await self._get_connection()
        if not pool or not self.embeddings:
            logger.error("Database connection or embeddings not initialized")
            return []

        try:
            stored_dim = await self._detect_stored_vector_dimensions(table_name)
            query_embedding = await self.embed_text(query, target_dimensions=stored_dim)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            candidates = HYBRID_SEARCH_CANDIDATES
            actual_dim = len(query_embedding)
            embedding_str = f"[{','.join(map(str, query_embedding))}]"

            async with pool.acquire() as conn:
                try:
                    vector_sql = f"""
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
                    vector_rows = await conn.fetch(
                        vector_sql, embedding_str, candidates
                    )
                except Exception as dim_error:
                    if "different vector dimensions" in str(dim_error):
                        logger.error(
                            f"Vector dimension mismatch in hybrid_search: Query embedding has {actual_dim} dimensions. "
                            f"Stored vectors have different dimensions. "
                            f"Please check your EMBEDDING_DIMENSIONS setting (currently {EMBEDDING_DIMENSIONS}) "
                            f"matches the dimensions of vectors stored in {table_name}."
                        )
                        logger.error(f"Full error: {dim_error}")

                        stored_dim = await self._detect_stored_vector_dimensions(
                            table_name
                        )
                        if stored_dim and stored_dim != actual_dim:
                            logger.info(
                                f"Retrying hybrid_search with detected stored dimensions: {stored_dim}"
                            )
                            query_embedding = await self.embed_text(
                                query, target_dimensions=stored_dim
                            )
                            if query_embedding:
                                embedding_str = (
                                    f"[{','.join(map(str, query_embedding))}]"
                                )
                                vector_rows = await conn.fetch(
                                    vector_sql, embedding_str, candidates
                                )
                            else:
                                raise
                        else:
                            raise
                    else:
                        raise

                vector_results = [
                    {
                        "id": str(row["id"]),
                        "content": row["content"] or "",
                        "metadata": row["metadata"] or {},
                        "similarity": float(row["similarity"]),
                    }
                    for row in vector_rows
                ]

                fts_results = await self._full_text_search(
                    query, table_name, candidates, conn
                )

                if fts_results:
                    logger.info(
                        f"Hybrid search: {len(vector_results)} vector results, {len(fts_results)} FTS results"
                    )
                    merged = self._reciprocal_rank_fusion(vector_results, fts_results)
                else:
                    logger.info(
                        f"Hybrid search: FTS unavailable, using {len(vector_results)} vector results only"
                    )
                    merged = vector_results

                final_limit = limit or self.max_results
                results = []
                filtered_count = 0

                for doc in merged[:candidates]:
                    similarity = doc.get("similarity") or doc.get("rrf_score", 0.0)
                    if similarity >= self.similarity_threshold:
                        results.append(doc)
                    else:
                        filtered_count += 1
                    if len(results) >= final_limit:
                        break

                if filtered_count > 0:
                    logger.debug(
                        f"Hybrid search filtered out {filtered_count} results below threshold {self.similarity_threshold}"
                    )

                if merged and not results:
                    max_similarity = max(
                        (
                            doc.get("similarity") or doc.get("rrf_score", 0.0)
                            for doc in merged[:candidates]
                        ),
                        default=0.0,
                    )
                    logger.warning(
                        f"Hybrid search: All {len(merged)} results filtered out by threshold {self.similarity_threshold}. "
                        f"Highest similarity score: {max_similarity:.3f}. Returning top {final_limit} results anyway."
                    )
                    results = merged[:final_limit]

                logger.info(
                    f"Hybrid search returned {len(results)} results from {table_name} (from {len(merged)} candidates)"
                )
                return results

        except Exception as e:
            logger.error(f"Error in hybrid search for {table_name}: {e}")
            return await self.search_similar(query, table_name, limit)

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

    async def check_whitelist_status(self, phone_number: str, bot_name: str) -> bool:
        pool = await self._get_connection()
        if not pool:
            logger.error("Database connection not initialized")
            return False

        whitelist_table = (
            "noi_cer_whitelist" if bot_name == "noi_cer" else "noi_energia_whitelist"
        )

        try:
            phone_number_bigint = int(phone_number.lstrip("+"))
        except (ValueError, AttributeError) as e:
            logger.warning(
                f"Invalid phone number format for whitelist check: {phone_number} - {e}"
            )
            return False

        try:
            async with pool.acquire() as conn:
                sql = f"""
                    SELECT whitelisted
                    FROM {whitelist_table}
                    WHERE phone_number = $1
                """
                row = await conn.fetchrow(sql, phone_number_bigint)

                if row is None:
                    logger.info(
                        f"Phone number {phone_number} not found in {whitelist_table}"
                    )
                    return False

                is_whitelisted = row["whitelisted"]
                if is_whitelisted:
                    logger.info(
                        f"Phone number {phone_number} is whitelisted in {whitelist_table}"
                    )
                else:
                    logger.info(
                        f"Phone number {phone_number} found but whitelisted=false in {whitelist_table}"
                    )
                return bool(is_whitelisted)

        except Exception as e:
            logger.error(
                f"Error checking whitelist status for {phone_number} in {whitelist_table}: {e}"
            )
            return False


supabase_store = SupabaseVectorStore()
