"""Tests for LLM adapters and prompt generation."""

import pytest
from kage.config import settings
from kage.llm.base import ChatMessage
from kage.llm.factory import get_llm
from kage.llm.prompt import get_system_prompt


def test_system_prompt_temporal_injection():
    """Verify system prompt contains timezone and security rules."""
    prompt = get_system_prompt()
    assert "Asia/Kolkata" in prompt
    assert "UNTRUSTED data" in prompt
    assert "Prompt Injection Defense" in prompt


@pytest.mark.asyncio
async def test_groq_llm_generation():
    """Verify live Groq LLM response generation with current key."""
    if not settings.groq_api_key:
        pytest.skip("GROQ_API_KEY not configured")

    llm = get_llm("groq")
    messages = [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Reply with exact word: PONG"),
    ]
    response = await llm.generate(messages=messages)
    assert response.content is not None
    assert "PONG" in response.content.upper()
