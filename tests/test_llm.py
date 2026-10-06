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


@pytest.mark.asyncio
async def test_groq_recovers_tool_use_failed(monkeypatch):
    """Verify GroqLLM seamlessly recovers tool calls from 400 tool_use_failed payload."""
    from kage.llm.groq import GroqLLM
    import httpx

    llm = GroqLLM(api_key="mock_key", model="mock_model")

    mock_error_payload = {
        "error": {
            "message": "Tool choice is none, but model called a tool",
            "type": "invalid_request_error",
            "code": "tool_use_failed",
            "failed_generation": '{"name": "web_search", "arguments": {"query": "Delhi weather"}}',
        }
    }

    mock_resp = httpx.Response(
        status_code=400,
        json=mock_error_payload,
        request=httpx.Request("POST", "https://api.groq.com"),
    )

    class MockAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, *args, **kwargs):
            return mock_resp

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockAsyncClient())

    messages = [ChatMessage(role="user", content="Delhi weather")]
    res = await llm.generate(messages=messages)
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].name == "web_search"
    assert res.tool_calls[0].arguments == {"query": "Delhi weather"}

