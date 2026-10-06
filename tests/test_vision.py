"""Tests for Vision and Voice modules."""

import pytest
from kage.audio.tts import synthesize_speech
from kage.vision.analyzer import analyze_image

# 1x1 transparent PNG
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00"
    b"\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.asyncio
async def test_tts_synthesis():
    """Verify that edge-tts produces non-empty audio bytes."""
    audio = await synthesize_speech("System check: audio synthesis online.")
    assert isinstance(audio, bytes)
    assert len(audio) > 1000


@pytest.mark.asyncio
async def test_vision_analyzer():
    """Verify that Groq Vision analyzer processes an image and returns a text response."""
    result = await analyze_image(TINY_PNG, prompt="What is this?", mime_type="image/png")
    assert isinstance(result, str)
    assert len(result) > 0
