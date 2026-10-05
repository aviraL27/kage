"""Base abstraction for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a structured tool/function call from the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """Normalized chat message structure."""
    role: str  # "system", "user", "assistant", "tool"
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None


class LLMResponse(BaseModel):
    """Normalized response from an LLM provider."""
    content: str = ""
    tool_calls: List[ToolCall] = Field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None


class BaseLLM(ABC):
    """Abstract interface for swappable LLM adapters."""

    @abstractmethod
    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Generate a response from the LLM given message history and optional tools."""
        pass
