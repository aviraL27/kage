"""Tests for Evening Debrief & Reflection engine."""

import pytest
from kage.scheduler.debrief import fetch_evening_debrief_data, generate_evening_debrief_text


def test_fetch_evening_debrief_data():
    """Verify evening debrief data collection."""
    data = fetch_evening_debrief_data()
    assert "date_str" in data
    assert "tomorrow_str" in data
    assert "completed_tasks" in data
    assert "pending_tasks" in data
    assert "tomorrow_events" in data


@pytest.mark.asyncio
async def test_generate_evening_debrief_text():
    """Verify LLM synthesis of evening debrief."""
    data = {
        "date_str": "Tuesday, October 06, 2026",
        "tomorrow_str": "Wednesday, October 07",
        "completed_tasks": [{"id": 1, "title": "Implement Voice & Vision", "status": "completed"}],
        "pending_tasks": [{"id": 2, "title": "Deploy to Cloud", "status": "pending"}],
        "tomorrow_events": [],
    }
    text = await generate_evening_debrief_text(data)
    assert isinstance(text, str)
    assert len(text) > 20
