"""Tests for Web Search and Web Page Reader tools."""

import pytest
from kage.tools.registry import registry
from kage.tools.web_tools import web_search, fetch_web_page


def test_web_tools_registered():
    """Verify web search and fetch tools are in registry."""
    assert registry.get_tool("web_search") is not None
    assert registry.get_tool("fetch_web_page") is not None


def test_web_search_execution():
    """Verify web_search returns results."""
    res = web_search("python programming", max_results=2)
    assert "count" in res
    assert "results" in res
    assert isinstance(res["results"], list)
    if res["results"]:
        first = res["results"][0]
        assert "title" in first
        assert "url" in first
        assert "[UNTRUSTED WEB CONTENT]:" in first["snippet"]
