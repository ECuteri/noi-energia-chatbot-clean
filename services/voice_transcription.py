import asyncio
import base64
import logging
from typing import Any, Dict, Optional

import aiohttp

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

MAX_AUDIO_SIZE_MB = 25
TIMEOUT_SECONDS = 30


async def transcribe_audio_from_url(audio_url: str) -> Optional[str]:
    return await _transcribe_with_gemini(audio_url)


async def _download_audio(
    audio_url: str, session: aiohttp.ClientSession
) -> Optional[tuple[bytes, str, float]]:
    logger.info(f"[voice] Downloading audio from: {audio_url}")

    async with session.get(audio_url) as response:
        if response.status != 200:
            logger.warning(f"[voice] Failed to download audio: HTTP {response.status}")
            return None

        audio_data = await response.read()

        if not audio_data:
            logger.warning(f"[voice] Empty audio file from {audio_url}")
            return None

        size_mb = len(audio_data) / (1024 * 1024)
        if size_mb > MAX_AUDIO_SIZE_MB:
            logger.warning(
                f"[voice] Audio file too large: {size_mb:.2f}MB (max {MAX_AUDIO_SIZE_MB}MB)"
            )
            return None

        logger.info(f"[voice] Downloaded {len(audio_data)} bytes ({size_mb:.2f}MB)")

        content_type = response.headers.get("Content-Type", "audio/ogg")

        return audio_data, content_type, size_mb


async def _transcribe_with_gemini(audio_url: str) -> Optional[str]:
    if not GEMINI_API_KEY:
        logger.error("[voice] Gemini API key not configured - cannot transcribe audio")
        return None

    try:
        import google.generativeai as genai

        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS, connect=10)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            download_result = await _download_audio(audio_url, session)
            if not download_result:
                return None

            audio_data, content_type, size_mb = download_result

            logger.info(f"[voice] Transcribing with Gemini 2.5 Flash...")

            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash-exp")

            mime_type = _get_mime_type_from_content_type(content_type)

            prompt = """Trascrivi questo messaggio vocale in italiano.
Restituisci SOLO il testo trascritto, senza commenti, spiegazioni o formattazione aggiuntiva.
Se il messaggio non contiene parlato o è silenzioso, restituisci: [audio silenzioso o non intellegibile]"""

            audio_part = {
                "mime_type": mime_type,
                "data": base64.b64encode(audio_data).decode("utf-8"),
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: model.generate_content([prompt, audio_part])
            )

            transcription = response.text.strip()

            if (
                transcription
                and transcription != "[audio silenzioso o non intellegibile]"
            ):
                logger.info(
                    f"[voice] ✅ Gemini transcription successful: {transcription[:100]}..."
                )
                return transcription
            else:
                logger.warning(
                    "[voice] Gemini returned empty or unintelligible transcription"
                )
                return None

    except ImportError:
        logger.error(
            "[voice] google-generativeai package not installed. Install with: pip install google-generativeai"
        )
        return None
    except aiohttp.ClientTimeout:
        logger.error(f"[voice] Timeout downloading audio from {audio_url}")
        return None
    except aiohttp.ClientConnectorError as conn_err:
        logger.error(f"[voice] Connection error downloading audio: {conn_err}")
        return None
    except Exception as e:
        logger.error(
            f"[voice] Error transcribing with Gemini from {audio_url}: {e}",
            exc_info=True,
        )
        return None


def _get_mime_type_from_content_type(content_type: str) -> str:
    content_type_lower = content_type.lower()

    if "ogg" in content_type_lower or "opus" in content_type_lower:
        return "audio/ogg"
    elif "mpeg" in content_type_lower or "mp3" in content_type_lower:
        return "audio/mpeg"
    elif "m4a" in content_type_lower:
        return "audio/mp4"
    elif "mp4" in content_type_lower:
        return "audio/mp4"
    elif "wav" in content_type_lower:
        return "audio/wav"
    elif "webm" in content_type_lower:
        return "audio/webm"
    elif "flac" in content_type_lower:
        return "audio/flac"
    else:
        return "audio/ogg"


async def process_message_attachments(
    attachments: list, content: str
) -> Dict[str, Any]:
    if not attachments:
        return {
            "final_content": content,
            "has_voice": False,
            "transcription": None,
            "attachment_urls": [],
        }

    attachment_urls = []
    transcriptions = []
    has_voice = False

    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue

        file_type = attachment.get("file_type", "").lower()
        data_url = attachment.get("data_url") or attachment.get("url")

        if not data_url:
            continue

        attachment_urls.append(data_url)

        if file_type in ("audio", "voice") or any(
            ext in data_url.lower() for ext in [".ogg", ".mp3", ".m4a", ".opus", ".wav"]
        ):
            has_voice = True
            logger.info(f"[voice] Detected voice message: {data_url}")

            transcription = await transcribe_audio_from_url(data_url)

            if transcription:
                transcriptions.append(transcription)
                logger.info(f"[voice] Added transcription: {transcription[:50]}...")
            else:
                logger.warning(f"[voice] Failed to transcribe audio from {data_url}")

    if transcriptions:
        combined_transcription = " ".join(transcriptions)

        if content and content.strip():
            final_content = (
                f"{content}\n\n[Messaggio vocale trascritto]: {combined_transcription}"
            )
        else:
            final_content = combined_transcription
    else:
        final_content = content

    return {
        "final_content": final_content,
        "has_voice": has_voice,
        "transcription": " ".join(transcriptions) if transcriptions else None,
        "attachment_urls": attachment_urls,
    }
