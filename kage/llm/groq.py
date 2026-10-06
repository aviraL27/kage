"""Groq LLM provider adapter."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
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

        import re
        max_retries = 4
        for attempt in range(max_retries):
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(self.BASE_URL, headers=headers, json=payload)
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_sec = 6.0
                    if "retry-after" in response.headers:
                        try:
                            wait_sec = float(response.headers["retry-after"])
                        except (ValueError, TypeError):
                            pass
                    elif "try again in" in response.text:
                        match = re.search(r"try again in ([\d\.]+)s", response.text)
                        if match:
                            wait_sec = float(match.group(1)) + 0.5
                    logger.warning(
                        f"Groq rate limit 429 reached. Waiting {wait_sec:.1f}s before retry (attempt {attempt + 1}/{max_retries})..."
                    )
                    await asyncio.sleep(wait_sec)
                    continue

                if response.status_code == 400:
                    try:
                        err_json = response.json()
                        err_detail = err_json.get("error", {})
                        if err_detail.get("code") == "tool_use_failed":
                            failed_gen = err_detail.get("failed_generation")
                            if failed_gen:
                                if isinstance(failed_gen, str):
                                    try:
                                        failed_gen = json.loads(failed_gen)
                                    except Exception:
                                        pass
                                if isinstance(failed_gen, dict) and "name" in failed_gen:
                                    logger.warning(
                                        f"Recovered tool call from Groq tool_use_failed: {failed_gen.get('name')}"
                                    )
                                    return LLMResponse(
                                        content="",
                                        tool_calls=[
                                            ToolCall(
                                                id=f"call_{int(time.time()*1000)}",
                                                name=failed_gen["name"],
                                                arguments=failed_gen.get("arguments", {}),
                                            )
                                        ],
                                        raw=err_json,
                                    )
                    except Exception as parse_err:
                        logger.warning(f"Could not parse Groq 400 error payload: {parse_err}")

                if response.status_code != 200:
                    logger.error(f"Groq API error {response.status_code}: {response.text}")
                    raise RuntimeError(f"Groq API error ({response.status_code}): {response.text}")

                data = response.json()
                choice = data["choices"][0]
                msg_data = choice["message"]
                break

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
