import logging
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import aiohttp

from config import CHATWOOT_ACCOUNT_ID, CHATWOOT_API_ACCESS_TOKEN, CHATWOOT_BASE_URL

logger = logging.getLogger(__name__)


def _is_configured() -> bool:
    return bool(CHATWOOT_BASE_URL and CHATWOOT_ACCOUNT_ID and CHATWOOT_API_ACCESS_TOKEN)


def _normalize_base_url(base_url: str) -> str:
    try:
        parsed = urlsplit(base_url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return base_url.rstrip("/")
    except Exception:
        return base_url.rstrip("/")


async def send_chatwoot_message(
    conversation_id: int,
    contact_identifier: str,
    *,
    text: Optional[str] = None,
    media_url: Optional[str] = None,
    caption: Optional[str] = None,
    private: bool = False,
    content_type: str = "text",
    content_attributes: Optional[Dict[str, Any]] = None,
    bot_token: Optional[str] = None,
) -> Dict[str, Any]:
    if not _is_configured():
        logger.error("Chatwoot env vars missing; cannot send message.")
        return {"status": "config_error", "detail": "Chatwoot configuration missing."}

    token = bot_token or CHATWOOT_API_ACCESS_TOKEN
    logger.debug(
        f"[chatwoot] Using token: {token[:10] if token else 'NONE'}... (bot_token provided: {bool(bot_token)})"
    )
    base_headers = {"api_access_token": token}
    base = _normalize_base_url(CHATWOOT_BASE_URL)
    url = f"{base}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages"

    timeout = aiohttp.ClientTimeout(total=10, connect=5)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            if media_url:
                form = aiohttp.FormData()
                form.add_field("content", caption or "")
                form.add_field("message_type", "outgoing")
                form.add_field("private", str(private).lower())

                try:
                    logger.debug("[chatwoot] Fetching media from URL: %s", media_url)
                    async with session.get(media_url) as r:
                        if r.status != 200:
                            error_detail = (
                                f"HTTP {r.status} when fetching media from {media_url}"
                            )
                            logger.warning("[chatwoot] %s", error_detail)
                            return {
                                "status": "media_link_invalid",
                                "detail": error_detail,
                                "url_checked": media_url,
                            }

                        content = await r.read()
                        if not content:
                            error_detail = f"Empty content received from {media_url}"
                            logger.warning("[chatwoot] %s", error_detail)
                            return {
                                "status": "media_link_invalid",
                                "detail": error_detail,
                                "url_checked": media_url,
                            }

                        filename = media_url.split("/")[-1] or "image.jpg"
                        form.add_field(
                            "attachments[]",
                            content,
                            filename=filename,
                            content_type=r.headers.get("Content-Type")
                            or "application/octet-stream",
                        )

                        logger.debug(
                            "[chatwoot] Successfully fetched media file: %s (%d bytes)",
                            filename,
                            len(content),
                        )

                except aiohttp.ClientConnectorError as conn_err:
                    error_detail = f"Connection failed to {media_url}: {str(conn_err)}"
                    if "Name does not resolve" in str(conn_err) or "getaddrinfo" in str(
                        conn_err
                    ):
                        error_detail = f"DNS resolution failed for {media_url}. Domain may not exist or be unreachable."
                    logger.warning("[chatwoot] %s", error_detail)
                    return {
                        "status": "media_link_invalid",
                        "detail": error_detail,
                        "url_checked": media_url,
                    }

                except aiohttp.ClientTimeout:
                    error_detail = f"Timeout fetching media from {media_url}"
                    logger.warning("[chatwoot] %s", error_detail)
                    return {
                        "status": "media_link_invalid",
                        "detail": error_detail,
                        "url_checked": media_url,
                    }

                except Exception as media_err:
                    error_detail = (
                        f"Error fetching media from {media_url}: {str(media_err)}"
                    )
                    logger.warning("[chatwoot] %s", error_detail)
                    return {
                        "status": "media_link_invalid",
                        "detail": error_detail,
                        "url_checked": media_url,
                    }

                try:
                    logger.debug("[chatwoot] Sending FormData to URL: %s", url)
                    async with session.post(
                        url, headers=base_headers, data=form
                    ) as resp:
                        detail = await resp.text()
                        logger.debug(
                            "[chatwoot] Response status: %d, body: %s",
                            resp.status,
                            detail[:500],
                        )
                        if resp.status in (200, 201):
                            logger.info("[chatwoot] Successfully sent media message")
                            return {"status": "success", "detail": detail}
                        error_detail = f"Chatwoot API returned {resp.status}: {detail}"
                        logger.warning("[chatwoot] %s", error_detail)
                        return {"status": "error", "detail": error_detail}
                except Exception as upload_err:
                    error_detail = (
                        f"Failed to upload media to Chatwoot: {str(upload_err)}"
                    )
                    logger.error("[chatwoot] %s", error_detail)
                    return {"status": "error", "detail": error_detail}
            else:
                payload = {
                    "content": text or "",
                    "message_type": "outgoing",
                    "private": private,
                    "content_type": content_type,
                    "content_attributes": content_attributes or {},
                }
                try:
                    logger.debug(
                        "[chatwoot] POST %s body_keys=%s", url, list(payload.keys())
                    )
                except Exception:
                    pass

                json_headers = {**base_headers, "Content-Type": "application/json"}
                async with session.post(
                    url, headers=json_headers, json=payload
                ) as resp:
                    detail = await resp.text()
                    if resp.status in (200, 201):
                        return {"status": "success", "detail": detail}
                    return {"status": "error", "detail": detail}
    except Exception as e:
        logger.error(f"Chatwoot send failed: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}
