"""Voice Out: Text-to-Speech synthesis using Microsoft Edge Neural Voices."""

from __future__ import annotations

import io
import logging
import os
import re
import edge_tts

logger = logging.getLogger(__name__)

# Default JARVIS voice: Refined, intelligent British English
DEFAULT_VOICE = os.getenv("JARVIS_VOICE", "en-GB-RyanNeural")


def _sanitize_for_tts(text: str) -> str:
    """Strip markdown formatting and symbols so the voice speaks clean sentences."""
    # Remove code blocks
    cleaned = re.sub(r"```[\s\S]*?```", " Code snippet. ", text)
    cleaned = re.sub(r"`[^`]*`", "", cleaned)
    # Convert markdown links [text](url) to text
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    # Remove markdown formatting characters
    cleaned = re.sub(r"[*_~#>-]", " ", cleaned)
    # Collapse multiple whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


async def synthesize_speech(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Synthesize text into high quality neural speech audio bytes (MP3).

    Args:
        text: Input string to speak.
        voice: Microsoft Edge neural voice identifier.

    Returns:
        MP3 audio bytes. Returns empty bytes on failure.
    """
    cleaned = _sanitize_for_tts(text)
    if not cleaned:
        return b""

    # Truncate overly long text for voice response (max ~600 chars for voice memos)
    if len(cleaned) > 800:
        cleaned = cleaned[:797] + "..."

    try:
        communicate = edge_tts.Communicate(cleaned, voice)
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])

        audio_bytes = buffer.getvalue()
        logger.info(f"Synthesized speech audio ({len(audio_bytes)} bytes) with voice '{voice}'")
        return audio_bytes
    except Exception as e:
        logger.error(f"Error during edge-tts speech synthesis: {e}", exc_info=True)
        return b""
