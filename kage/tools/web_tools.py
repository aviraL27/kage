"""Live Web Search and Web Page Reader tools using DuckDuckGo and Jina Reader."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import httpx
from duckduckgo_search import DDGS
from pydantic import BaseModel, Field

from kage.tools.registry import registry

logger = logging.getLogger(__name__)


# =====================================================================
# Argument Schemas
# =====================================================================

class WebSearchArgs(BaseModel):
    query: str = Field(
        ...,
        description="Search query to look up on the web (e.g. 'latest AI news today', 'Python 3.12 release date').",
    )
    max_results: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum number of search results to return (1-10).",
    )


class FetchWebPageArgs(BaseModel):
    url: str = Field(
        ...,
        description="The full HTTP/HTTPS URL of the article, documentation, or webpage to read.",
    )


# =====================================================================
# Tool Implementations
# =====================================================================

@registry.register(
    name="web_search",
    description="Perform a real-time web search for current news, facts, articles, and documentation.",
    args_schema=WebSearchArgs,
)
def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Perform real-time web search using DuckDuckGo."""
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))

        formatted = []
        for r in raw_results:
            formatted.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": f"[UNTRUSTED WEB CONTENT]: {r.get('body', '')[:300]}",
            })

        return {
            "count": len(formatted),
            "query": query,
            "results": formatted,
        }
    except Exception as e:
        logger.error(f"Error performing web search for '{query}': {e}", exc_info=True)
        return {"error": f"Web search failed: {str(e)}"}


@registry.register(
    name="fetch_web_page",
    description="Fetch and extract the readable markdown content of any webpage or article URL using Jina Reader.",
    args_schema=FetchWebPageArgs,
)
def fetch_web_page(url: str) -> Dict[str, Any]:
    """Fetch readable content from a URL via Jina Reader."""
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "Accept": "text/plain",
        "User-Agent": "KageAgent/1.0",
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(jina_url, headers=headers)
            response.raise_for_status()
            text = response.text.strip()

            # Truncate to 3000 chars to avoid overflowing LLM context window
            preview = text[:3000]

            return {
                "url": url,
                "content": f"[UNTRUSTED WEB CONTENT]:\n{preview}",
                "length": len(text),
            }
    except Exception as e:
        logger.error(f"Error reading web page '{url}': {e}", exc_info=True)
        return {"error": f"Failed to fetch webpage: {str(e)}"}
