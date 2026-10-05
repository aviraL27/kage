"""Unit tests for SQLite tasks and reminders database layer."""

import pytest
from datetime import datetime, timedelta
from kage.config import settings
from kage.db.database import init_db
from kage.db import tasks as db_tasks


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_create_and_get_task():
    task = db_tasks.create_task(
        title="Write integration tests",
        due_date="2026-10-06T18:00:00+05:30",
        description="Verify Phase 2 requirements",
    )
    assert task["id"] is not None
    assert task["title"] == "Write integration tests"
    assert task["status"] == "pending"

    fetched = db_tasks.get_task(task["id"])
    assert fetched is not None
    assert fetched["title"] == "Write integration tests"


def test_list_tasks_filtering():
    now = datetime.now(settings.tz)
    today_due = now.replace(hour=14, minute=0, second=0).isoformat()
    future_due = (now + timedelta(days=20)).isoformat()

    t1 = db_tasks.create_task("Task for today", due_date=today_due)
    t2 = db_tasks.create_task("Task far future", due_date=future_due)

    # Filter pending
    pending = db_tasks.list_tasks(status="pending")
    titles = [t["title"] for t in pending]
    assert "Task for today" in titles
    assert "Task far future" in titles

    # Filter today
    today_tasks = db_tasks.list_tasks(status="pending", period="today")
    today_titles = [t["title"] for t in today_tasks]
    assert "Task for today" in today_titles
    assert "Task far future" not in today_titles


def test_complete_and_delete_task():
    task = db_tasks.create_task("Temporary task")
    assert task["status"] == "pending"

    completed = db_tasks.complete_task(task["id"])
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None

    deleted = db_tasks.delete_task(task["id"])
    assert deleted is True
    assert db_tasks.get_task(task["id"]) is None


def test_create_and_update_reminder():
    rem = db_tasks.create_reminder(
        remind_at="2026-10-06T10:00:00+05:30",
        message="Review PRs",
    )
    assert rem["id"] is not None
    assert rem["status"] == "scheduled"

    db_tasks.update_reminder_status(rem["id"], "fired", job_id="job_123")
    reminders = db_tasks.list_reminders(status="fired")
    assert any(r["id"] == rem["id"] for r in reminders)
