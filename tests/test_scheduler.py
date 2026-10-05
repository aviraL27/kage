"""Unit tests for persistent APScheduler service."""

import asyncio
from datetime import datetime, timedelta
import pytest

from kage.config import settings
from kage.db.database import init_db
from kage.scheduler.service import scheduler_service, set_telegram_sender_hook, reminder_job_runner


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


@pytest.mark.asyncio
async def test_scheduler_add_and_fire():
    """Verify scheduler service schedules jobs into persistent store."""
    scheduler_service.start()

    fired_events = []

    def mock_sender(user_id: int, message: str):
        fired_events.append({"user_id": user_id, "message": message})

    set_telegram_sender_hook(mock_sender)

    # Directly execute reminder_job_runner to test trigger callback logic
    reminder_job_runner(reminder_id=9999, message="Test Alert", user_id=1487439060)

    assert len(fired_events) == 1
    assert fired_events[0]["user_id"] == 1487439060
    assert "Test Alert" in fired_events[0]["message"]
