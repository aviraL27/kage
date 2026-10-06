"""Multimodal vision analyzer using Groq's llama-3.2-11b-vision-preview."""

from __future__ import annotations

import base64
import logging
import httpx

from kage.config import settings

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
VISION_MODEL = "llama-3.2-11b-vision-preview"


async def analyze_image(
    image_bytes: bytes,
    prompt: str = "Analyze this image and extract all relevant information, text, tasks, dates, and details.",
    mime_type: str = "image/jpeg",
) -> str:
    """Analyze an image buffer using Groq's multimodal vision model.

    Args:
        image_bytes: Raw bytes of the image (JPEG, PNG, WebP).
        prompt: Question, instructions, or user caption.
        mime_type: MIME type of the image.

    Returns:
        Structured text description and analysis.
    """
    if not settings.groq_api_key:
        logger.error("GROQ_API_KEY is not set. Vision analysis unavailable.")
        return "Vision analysis unavailable: GROQ_API_KEY is missing."

    encoded_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:{mime_type};base64,{encoded_b64}"

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"You are the visual cortex for Kage, a personal AI command center agent. "
                            f"The user shared this image with you. Follow the user's instructions carefully.\n\n"
                            f"USER PROMPT / CAPTION: {prompt}"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_uri,
                        },
                    },
                ],
            }
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(GROQ_CHAT_URL, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            analysis = result["choices"][0]["message"]["content"]
            logger.info("Vision analysis completed successfully.")
            return analysis
    except Exception as e:
        logger.error(f"Error during vision analysis: {e}", exc_info=True)
        return f"Could not analyze image due to error: {str(e)}"
