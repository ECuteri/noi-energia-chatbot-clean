import logging
from typing import Dict, List

import httpx

from config import OPENROUTER_API_KEY, RERANK_ENABLED, RERANK_MODEL, RERANK_TOP_N

logger = logging.getLogger(__name__)

OPENROUTER_RERANK_URL = "https://openrouter.ai/api/v1/rerank"


async def rerank_results(
    query: str,
    documents: List[Dict],
    top_n: int = None,
) -> List[Dict]:
    if not RERANK_ENABLED:
        logger.debug("Reranking disabled, returning original results")
        return documents

    if not documents:
        return []

    if not OPENROUTER_API_KEY:
        logger.warning("OpenRouter API key not set, skipping reranking")
        return documents

    top_n = top_n or RERANK_TOP_N

    try:
        doc_texts = [doc.get("content", "") for doc in documents]

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_RERANK_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://noienergia.com",
                    "X-Title": "NOI Energia Chatbot",
                },
                json={
                    "model": RERANK_MODEL,
                    "query": query,
                    "documents": doc_texts,
                    "top_n": min(top_n, len(documents)),
                },
            )

            if response.status_code != 200:
                logger.error(
                    f"Reranker API error: {response.status_code} - {response.text}"
                )
                return documents[:top_n]

            response_text = response.text.strip()
            if not response_text:
                logger.error("Reranker API returned empty response")
                return documents[:top_n]

            try:
                data = response.json()
            except ValueError as json_error:
                logger.error(
                    f"Reranker API returned invalid JSON: {response_text[:200]} - {json_error}"
                )
                return documents[:top_n]

            results = data.get("data", [])

            reranked = []
            for result in results:
                idx = result.get("index")
                if idx is not None and idx < len(documents):
                    doc = documents[idx].copy()
                    doc["rerank_score"] = result.get("relevance_score", 0)
                    reranked.append(doc)

            logger.info(
                f"Reranked {len(documents)} documents to top {len(reranked)} using {RERANK_MODEL}"
            )
            return reranked

    except httpx.TimeoutException:
        logger.error("Reranker request timed out")
        return documents[:top_n]
    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        return documents[:top_n]
