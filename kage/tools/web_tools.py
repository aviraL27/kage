"""Live Web Search and Web Page Reader tools using DuckDuckGo and Jina Reader."""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import unquote
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

def _scrape_ddg_html(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Scrape DuckDuckGo HTML / Lite endpoints directly for fast, unblocked search results."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    endpoints = [
        "https://html.duckduckgo.com/html/",
        "https://lite.duckduckgo.com/lite/",
    ]
    for endpoint in endpoints:
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.post(endpoint, data={"q": query}, headers=headers)
                if resp.status_code != 200:
                    continue

                blocks = re.findall(
                    r'<div class="[^"]*result results_links[^"]*"[^>]*>(.*?)(?=<div class="[^"]*result results_links|\Z)',
                    resp.text,
                    re.DOTALL,
                )
                results: List[Dict[str, str]] = []
                for b in blocks:
                    snippet_match = re.search(r'<a[^>]+class="result__snippet[^"]*"[^>]*>(.*?)</a>', b, re.DOTALL)
                    snippet = html.unescape(re.sub(r'<[^>]+>', '', snippet_match.group(1))).strip() if snippet_match else ""

                    link_match = re.search(r'<a[^>]+class="result__url"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.DOTALL)
                    title_head = re.search(r'<h2[^>]*class="result__title"[^>]*>.*?<a[^>]*>(.*?)</a>', b, re.DOTALL)
                    title = html.unescape(re.sub(r'<[^>]+>', '', title_head.group(1))).strip() if title_head else ""
                    raw_url = link_match.group(1).strip() if link_match else ""

                    uddg = re.search(r'uddg=([^&]+)', raw_url)
                    url = unquote(uddg.group(1)) if uddg else raw_url
                    if not url.startswith("http"):
                        url = f"https://{url}" if url else ""

                    if title or snippet:
                        results.append({
                            "title": title or "Search Result",
                            "url": url,
                            "snippet": f"[UNTRUSTED WEB CONTENT]: {snippet[:300]}",
                        })
                    if len(results) >= max_results:
                        break

                if results:
                    return results
        except Exception as e:
            logger.debug(f"Direct DDG scrape on {endpoint} failed: {e}")

    return []


@registry.register(
    name="web_search",
    description="Perform a real-time web search for current news, facts, articles, and documentation.",
    args_schema=WebSearchArgs,
)
def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Perform real-time web search using direct DuckDuckGo HTML scraping with DDGS fallback."""
    try:
        # 1. Primary: Direct HTML/Lite scraping (unblocked and fast)
        results = _scrape_ddg_html(query, max_results=max_results)

        # 2. Secondary: Fallback to duckduckgo_search library
        if not results:
            try:
                with DDGS() as ddgs:
                    raw_results = list(ddgs.text(query, max_results=max_results))
                for r in raw_results:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": f"[UNTRUSTED WEB CONTENT]: {r.get('body', '')[:300]}",
                    })
            except Exception as e:
                logger.debug(f"DDGS library fallback failed: {e}")

        return {
            "count": len(results),
            "query": query,
            "results": results,
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
