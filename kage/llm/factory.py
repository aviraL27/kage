"""Factory for instantiating the active LLM provider."""

from __future__ import annotations

import logging
from kage.config import settings
from kage.llm.base import BaseLLM
from kage.llm.groq import GroqLLM
from kage.llm.gemini import GeminiLLM

logger = logging.getLogger(__name__)


def get_llm(provider: str | None = None) -> BaseLLM:
    """Return the configured LLM adapter instance."""
    prov = (provider or settings.llm_provider).lower()
    
    if prov == "groq":
        return GroqLLM()
    elif prov == "gemini":
        return GeminiLLM()
    else:
        # Default fallback to Groq
        logger.info(f"Unknown provider '{prov}', defaulting to Groq.")
        return GroqLLM()
