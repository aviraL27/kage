"""Unit and integration tests for Morning Brief feature."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Update, User, Chat, Message

from kage.db.database import init_db
from kage.scheduler.brief import (
    fetch_brief_raw_data,
    generate_morning_brief_text,
    schedule_morning_brief_cron,
)
from kage.scheduler.service import scheduler_service
from kage.bot.handlers import brief_command


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_fetch_brief_raw_data():
    """Verify raw data collection from tasks, calendar, gmail, and github."""
    data = fetch_brief_raw_data()
    assert "date_str" in data
    assert "today_tasks" in data
    assert "calendar_events" in data
    assert "unread_emails" in data
    assert "github_notifications" in data


@pytest.mark.asyncio
async def test_generate_morning_brief_text():
    """Verify LLM morning brief text generation."""
    mock_data = {
        "date_str": "Tuesday, October 06, 2026",
        "time_str": "07:30 AM IST",
        "today_tasks": [{"id": 1, "title": "Deploy Kage agent", "due_date": "2026-10-06T18:00:00+05:30"}],
        "total_pending_tasks": 1,
        "calendar_events": [{"summary": "Daily Standup", "start": "2026-10-06T10:00:00+05:30", "end": "2026-10-06T10:30:00+05:30"}],
        "unread_emails": [{"subject": "Security notice", "sender": "security@test.com", "snippet": "Everything secure"}],
        "github_notifications": [{"repository": "aviraL27/kage", "title": "PR #1 merged", "type": "PullRequest"}],
    }
    brief = await generate_morning_brief_text(mock_data)
    assert len(brief) > 50
    # Should include greeting or section
    assert any(term in brief for term in ["Morning", "Deploy", "Standup", "Tasks", "Schedule"])


def test_schedule_morning_brief_cron():
    """Verify APScheduler has the 7:30 AM IST recurring job."""
    scheduler_service.start()
    schedule_morning_brief_cron()

    job = scheduler_service.scheduler.get_job("daily_morning_brief")
    assert job is not None
    assert str(job.trigger) == "cron[hour='7', minute='30']"


@pytest.mark.asyncio
async def test_brief_command_handler():
    """Verify /brief command handler triggers and replies."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = 1487439060
    update.effective_user = user

    chat = MagicMock(spec=Chat)
    chat.id = 1487439060
    update.effective_chat = chat

    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    update.effective_message = message

    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()

    await brief_command(update, context)

    context.bot.send_chat_action.assert_called_once()
    message.reply_text.assert_called_once()
    reply_text = message.reply_text.call_args[0][0]
    assert len(reply_text) > 0
