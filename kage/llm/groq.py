"""Groq LLM provider adapter."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from kage.config import settings
from kage.llm.base import BaseLLM, ChatMessage, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class GroqLLM(BaseLLM):
    """Groq API adapter using async HTTP requests."""

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        if not self.api_key:
            raise ValueError("Groq API key not provided in settings or constructor.")

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Call Groq chat completions API with message history and optional tools."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Convert messages to OpenAI compatible dicts
        formatted_messages = []
        for msg in messages:
            entry: Dict[str, Any] = {"role": msg.role}
            if msg.content is not None:
                entry["content"] = msg.content
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            formatted_messages.append(entry)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(self.BASE_URL, headers=headers, json=payload)
            if response.status_code != 200:
                logger.error(f"Groq API error {response.status_code}: {response.text}")
                raise RuntimeError(f"Groq API error ({response.status_code}): {response.text}")

            data = response.json()
            choice = data["choices"][0]
            msg_data = choice["message"]

            parsed_tool_calls: List[ToolCall] = []
            if "tool_calls" in msg_data and msg_data["tool_calls"]:
                for raw_tc in msg_data["tool_calls"]:
                    fn_data = raw_tc.get("function", {})
                    fn_args_str = fn_data.get("arguments", "{}")
                    try:
                        fn_args = json.loads(fn_args_str) if isinstance(fn_args_str, str) else fn_args_str
                    except Exception:
                        fn_args = {}
                    parsed_tool_calls.append(
                        ToolCall(
                            id=raw_tc.get("id", ""),
                            name=fn_data.get("name", ""),
                            arguments=fn_args,
                        )
                    )

            return LLMResponse(
                content=msg_data.get("content") or "",
                tool_calls=parsed_tool_calls,
                raw=data,
            )
