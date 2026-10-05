"""Gemini LLM provider adapter using official google-genai SDK or REST API."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import httpx

from kage.config import settings
from kage.llm.base import BaseLLM, ChatMessage, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class GeminiLLM(BaseLLM):
    """Google Gemini free-tier provider adapter."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash") -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = model
        if not self.api_key:
            logger.warning("Gemini API key not configured.")

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Call Gemini REST endpoint."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        contents = []
        system_instruction = None

        for msg in messages:
            if msg.role == "system":
                system_instruction = {"parts": [{"text": msg.content or ""}]}
            else:
                role = "user" if msg.role == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.content or ""}]
                })

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")
            
            data = resp.json()
            candidates = data.get("candidates", [])
            text_out = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text_out = "".join(p.get("text", "") for p in parts)

            return LLMResponse(content=text_out, tool_calls=[], raw=data)
