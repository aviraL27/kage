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


def test_schedule_evening_debrief_cron():
    """Verify APScheduler registers the 9:30 PM IST daily debrief job."""
    from kage.scheduler.debrief import schedule_evening_debrief_cron
    from kage.scheduler.service import scheduler_service

    scheduler_service.start()
    schedule_evening_debrief_cron()

    job = scheduler_service.scheduler.get_job("daily_evening_debrief")
    assert job is not None
    assert str(job.trigger) == "cron[hour='21', minute='30']"

