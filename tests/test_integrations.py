"""Integration tests for Google Calendar, Gmail, and GitHub tools."""

import pytest
from kage.config import settings
from kage.tools.registry import registry
import kage.tools  # Register tools


@pytest.mark.asyncio
async def test_google_calendar_tool():
    """Verify list_calendar_events execution via registry."""
    if not settings.google_token_file.exists():
        pytest.skip("token.json not present")

    res = await registry.execute("list_calendar_events", {"max_results": 5})
    assert res["success"] is True
    result = res["result"]
    assert "count" in result
    assert "events" in result
    assert isinstance(result["events"], list)


@pytest.mark.asyncio
async def test_gmail_unread_emails_tool():
    """Verify list_unread_emails execution via registry with untrusted wrapping."""
    if not settings.google_token_file.exists():
        pytest.skip("token.json not present")

    res = await registry.execute("list_unread_emails", {"max_results": 3})
    assert res["success"] is True
    result = res["result"]
    assert "count" in result
    assert "emails" in result
    for email in result["emails"]:
        assert "[UNTRUSTED EMAIL CONTENT]:" in email["snippet"]
        assert "subject" in email
        assert "sender" in email


@pytest.mark.asyncio
async def test_github_notifications_tool():
    """Verify list_github_notifications execution via registry with untrusted wrapping."""
    if not settings.github_token:
        pytest.skip("GITHUB_TOKEN not present")

    res = await registry.execute("list_github_notifications", {"max_results": 5})
    assert res["success"] is True
    result = res["result"]
    assert "count" in result
    assert "notifications" in result
    for notif in result["notifications"]:
        assert "[UNTRUSTED GITHUB CONTENT]:" in notif["title"]
        assert "repository" in notif


def test_tool_registry_has_phase3_tools():
    """Verify all phase 3 tools are registered."""
    assert registry.get_tool("list_calendar_events") is not None
    assert registry.get_tool("list_unread_emails") is not None
    assert registry.get_tool("list_github_notifications") is not None
