"""Voice In: Speech-to-Text transcription using Groq's whisper-large-v3-turbo."""

from __future__ import annotations

import logging
import httpx

from kage.config import settings

logger = logging.getLogger(__name__)

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
WHISPER_MODEL = "whisper-large-v3-turbo"


async def transcribe_audio(audio_bytes: bytes, filename: str = "voice.oga") -> str:
    """Transcribe an audio buffer (e.g. Telegram voice memo) using Groq Whisper.

    Args:
        audio_bytes: Raw bytes of the audio recording (OGG, MP3, WAV, etc.).
        filename: Name of the file with appropriate extension.

    Returns:
        Transcribed string. Returns empty string if transcription fails.
    """
    if not settings.groq_api_key:
        logger.error("GROQ_API_KEY is not set. Audio transcription unavailable.")
        return ""

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
    }

    files = {
        "file": (filename, audio_bytes, "audio/ogg"),
    }
    data = {
        "model": WHISPER_MODEL,
        "response_format": "json",
        "temperature": "0.0",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GROQ_TRANSCRIPTION_URL,
                headers=headers,
                files=files,
                data=data,
            )
            response.raise_for_status()
            result = response.json()
            transcription = result.get("text", "").strip()
            logger.info(f"Groq Whisper transcription success: '{transcription[:80]}...'")
            return transcription
    except Exception as e:
        logger.error(f"Error during audio transcription with Groq Whisper: {e}", exc_info=True)
        return ""
