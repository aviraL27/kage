"""Unit tests for tool registry, validation, and task/reminder tools."""

import json
from datetime import datetime, timedelta
import pytest
from pathlib import Path

from kage.config import settings
from kage.db.database import init_db, get_db_connection
from kage.db.audit import TOOL_LOG_FILE
from kage.tools.registry import registry
import kage.tools.tasks  # registers tools


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


@pytest.mark.asyncio
async def test_add_and_list_task_tools():
    """Verify add_task and list_tasks via tool registry."""
    # Execute add_task
    add_res = await registry.execute(
        "add_task",
        {"title": "Tool Created Task", "description": "Created via registry"},
    )
    assert add_res["success"] is True
    assert "Task #" in add_res["result"]["message"]
    task_id = add_res["result"]["task"]["id"]

    # Execute list_tasks
    list_res = await registry.execute("list_tasks", {"status": "pending"})
    assert list_res["success"] is True
    assert list_res["result"]["count"] >= 1
    titles = [t["title"] for t in list_res["result"]["tasks"]]
    assert "Tool Created Task" in titles

    # Execute complete_task
    comp_res = await registry.execute("complete_task", {"task_id": task_id})
    assert comp_res["success"] is True
    assert comp_res["result"]["task"]["status"] == "completed"


@pytest.mark.asyncio
async def test_delete_task_confirmation_policy():
    """Verify delete_task requires explicit confirmation flag."""
    add_res = await registry.execute("add_task", {"title": "Task To Delete"})
    task_id = add_res["result"]["task"]["id"]

    # Without confirmation -> must prompt for confirmation
    del_res_unconfirmed = await registry.execute("delete_task", {"task_id": task_id, "confirmed": False})
    assert del_res_unconfirmed["success"] is True
    assert del_res_unconfirmed["result"].get("confirmation_required") is True

    # With confirmation -> must delete
    del_res_confirmed = await registry.execute("delete_task", {"task_id": task_id, "confirmed": True})
    assert del_res_confirmed["success"] is True
    assert "successfully deleted" in del_res_confirmed["result"]["message"]


@pytest.mark.asyncio
async def test_set_reminder_validation():
    """Verify set_reminder validates timestamps and rejects past dates."""
    # Past timestamp must be rejected
    past_iso = (datetime.now(settings.tz) - timedelta(hours=2)).isoformat()
    past_res = await registry.execute(
        "set_reminder",
        {"message": "Past reminder", "remind_at": past_iso},
    )
    assert past_res["success"] is True
    assert "in the past" in past_res["result"].get("error", "")

    # Future timestamp must succeed
    future_iso = (datetime.now(settings.tz) + timedelta(hours=2)).isoformat()
    future_res = await registry.execute(
        "set_reminder",
        {"message": "Future reminder", "remind_at": future_iso},
    )
    assert future_res["success"] is True
    assert "Reminder scheduled" in future_res["result"]["message"]


@pytest.mark.asyncio
async def test_tool_audit_logging():
    """Verify tool execution is logged both to SQLite and logs/tool_calls.log."""
    await registry.execute("list_tasks", {"status": "pending"})

    # Check log file exists and has content
    assert TOOL_LOG_FILE.exists()
    content = TOOL_LOG_FILE.read_text(encoding="utf-8")
    assert "tool=list_tasks" in content

    # Check SQLite audit table
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM tool_audit_logs WHERE tool_name = 'list_tasks' ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["tool_name"] == "list_tasks"
        assert row["status"] == "success"
        assert row["latency_ms"] >= 0
