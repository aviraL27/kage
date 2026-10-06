"""FastMCP server exposing Kage command-center tools.

This module provides a Model Context Protocol (MCP) server using the official
FastMCP SDK. It exposes all Kage capabilities (task management, reminders,
memory, Google Calendar, Gmail, and GitHub) as standardized MCP tools.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import Annotated, Any, Dict, Optional
from pydantic import Field
from mcp.server.fastmcp import FastMCP

from kage.config import settings
from kage.db import memory as db_memory
from kage.db import tasks as db_tasks
from kage.scheduler.service import scheduler_service
from kage.tools import github_tools, google_tools

logger = logging.getLogger(__name__)

# Initialize FastMCP Server
mcp_server = FastMCP(
    name="kage-server",
    instructions=(
        "Kage Personal Command Center MCP server providing task management, "
        "persistent memory, calendar events, unread emails, and GitHub notifications."
    ),
)


# =====================================================================
# 1. Task & Reminder Tools
# =====================================================================

@mcp_server.tool()
def add_task(
    title: Annotated[str, Field(description="Clear title or summary of the task to be done.")],
    due_date: Annotated[
        Optional[str],
        Field(
            description="Optional due date/time in ISO-8601 format (e.g. '2026-10-06T18:00:00+05:30') in Asia/Kolkata timezone."
        ),
    ] = None,
    description: Annotated[
        str,
        Field(description="Optional additional details, context, or notes for the task."),
    ] = "",
) -> Dict[str, Any]:
    """Create a new task on the user's task list with an optional due date."""
    task = db_tasks.create_task(title=title, due_date=due_date, description=description)
    return {
        "message": f"Task #{task['id']} created: '{task['title']}'",
        "task": task,
    }


@mcp_server.tool()
def list_tasks(
    status: Annotated[
        str,
        Field(description="Status filter: 'pending', 'completed', or 'all'. Defaults to 'pending'."),
    ] = "pending",
    period: Annotated[
        Optional[str],
        Field(description="Optional period filter: 'today', 'this_week', or None for all."),
    ] = None,
) -> Dict[str, Any]:
    """List tasks from the database filtered by status ('pending', 'completed', 'all') and period ('today', 'this_week')."""
    tasks = db_tasks.list_tasks(status=status, period=period)
    return {
        "count": len(tasks),
        "tasks": tasks,
    }


@mcp_server.tool()
def complete_task(
    task_id: Annotated[int, Field(description="The numeric ID of the task to complete.")],
) -> Dict[str, Any]:
    """Mark a task as completed given its numeric ID."""
    task = db_tasks.get_task(task_id)
    if not task:
        return {"error": f"Task #{task_id} not found."}

    updated = db_tasks.complete_task(task_id)
    return {
        "message": f"Task #{task_id} ('{task['title']}') marked as completed.",
        "task": updated,
    }


@mcp_server.tool()
def delete_task(
    task_id: Annotated[int, Field(description="The numeric ID of the task to delete.")],
    confirmed: Annotated[
        bool,
        Field(description="Explicit user confirmation flag. Must be true to delete permanently."),
    ] = False,
) -> Dict[str, Any]:
    """Delete a task by its numeric ID. Always invoke this tool when the user asks to delete or remove a task; confirmation is handled by the system."""
    task = db_tasks.get_task(task_id)
    if not task:
        return {"error": f"Task #{task_id} not found."}

    if not confirmed:
        return {
            "confirmation_required": True,
            "action": "delete_task",
            "task_id": task_id,
            "message": f"Are you sure you want to delete task #{task_id} ('{task['title']}')?",
        }

    deleted = db_tasks.delete_task(task_id)
    if deleted:
        return {"message": f"Task #{task_id} ('{task['title']}') was successfully deleted."}
    return {"error": f"Failed to delete task #{task_id}."}


@mcp_server.tool()
def set_reminder(
    message: Annotated[
        str,
        Field(description="The message or alert to send when the reminder triggers."),
    ],
    remind_at: Annotated[
        str,
        Field(
            description="Exact date and time to fire the reminder in ISO-8601 format (e.g. '2026-10-06T18:00:00+05:30') in Asia/Kolkata timezone."
        ),
    ],
    task_id: Annotated[
        Optional[int],
        Field(description="Optional task ID associated with this reminder."),
    ] = None,
) -> Dict[str, Any]:
    """Schedule an alert or reminder for a specific date and time in ISO-8601 format."""
    try:
        dt = datetime.fromisoformat(remind_at)
    except ValueError:
        return {"error": f"Invalid ISO-8601 format for remind_at: '{remind_at}'."}

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=settings.tz)
    else:
        dt = dt.astimezone(settings.tz)

    now = datetime.now(settings.tz)
    if dt <= now:
        return {"error": f"Reminder time {dt.isoformat()} is in the past! Current time is {now.isoformat()}."}

    reminder = scheduler_service.schedule_reminder(
        remind_at=dt,
        message=message,
        task_id=task_id,
    )
    return {
        "message": f"Reminder scheduled for {dt.strftime('%A, %b %d %I:%M %p')}: '{message}'",
        "reminder": reminder,
    }


# =====================================================================
# 2. Memory Tools
# =====================================================================

@mcp_server.tool()
def remember_fact(
    key: Annotated[
        str,
        Field(description="A short unique descriptor or topic for the memory (e.g. 'favorite_drink', 'working_hours')."),
    ],
    value: Annotated[
        str,
        Field(description="The detailed fact, preference, or rule to remember."),
    ],
    category: Annotated[
        str,
        Field(description="Category classification: 'preference', 'fact', 'routine', or 'general'."),
    ] = "general",
) -> Dict[str, Any]:
    """Save or update a persistent user preference, fact, or instruction in SQLite that survives across sessions."""
    saved = db_memory.set_memory(key=key, value=value, category=category)
    return {
        "message": f"Successfully remembered [{saved['category'].upper()}] '{saved['key']}': {saved['value']}",
        "memory": saved,
    }


@mcp_server.tool()
def forget_fact(
    key: Annotated[str, Field(description="The unique key of the memory to remove.")],
) -> Dict[str, Any]:
    """Remove a previously stored fact or preference from persistent memory."""
    deleted = db_memory.delete_memory(key=key)
    if deleted:
        return {"message": f"Successfully forgot memory '{key}'."}
    return {"error": f"Memory with key '{key}' was not found."}


@mcp_server.tool()
def list_memories(
    category: Annotated[
        Optional[str],
        Field(description="Optional filter by category ('preference', 'fact', 'routine', 'general')."),
    ] = None,
) -> Dict[str, Any]:
    """List all persistent memories, preferences, and facts stored across sessions."""
    memories = db_memory.list_memories(category=category)
    return {
        "count": len(memories),
        "memories": memories,
    }


# =====================================================================
# 3. Google Calendar & Gmail Tools (Read-Only)
# =====================================================================

@mcp_server.tool()
def list_calendar_events(
    start_date: Annotated[
        Optional[str],
        Field(description="Start ISO-8601 date/time (defaults to start of today in Asia/Kolkata)."),
    ] = None,
    end_date: Annotated[
        Optional[str],
        Field(description="End ISO-8601 date/time (defaults to end of today in Asia/Kolkata)."),
    ] = None,
    max_results: Annotated[
        int,
        Field(description="Maximum number of events to fetch (1-50).", ge=1, le=50),
    ] = 10,
) -> Dict[str, Any]:
    """Fetch upcoming calendar events from Google Calendar. Read-only."""
    return google_tools.list_calendar_events(
        start_date=start_date,
        end_date=end_date,
        max_results=max_results,
    )


@mcp_server.tool()
def list_unread_emails(
    max_results: Annotated[
        int,
        Field(description="Maximum number of unread emails to retrieve (1-20).", ge=1, le=20),
    ] = 5,
) -> Dict[str, Any]:
    """Fetch recent unread emails from Gmail with subjects, senders, and safe summaries. Read-only."""
    return google_tools.list_unread_emails(max_results=max_results)


# =====================================================================
# 4. GitHub Notifications Tool (Read-Only)
# =====================================================================

@mcp_server.tool()
def list_github_notifications(
    all: Annotated[
        bool,
        Field(description="If true, shows all notifications including read ones. Defaults to false (unread only)."),
    ] = False,
    max_results: Annotated[
        int,
        Field(description="Maximum number of notifications to retrieve (1-50).", ge=1, le=50),
    ] = 10,
) -> Dict[str, Any]:
    """Fetch unread GitHub notifications and mentions for repositories you participate in. Read-only."""
    return github_tools.list_github_notifications(all=all, max_results=max_results)


# =====================================================================
# Server Entrypoint
# =====================================================================

def run_server() -> None:
    """Run FastMCP server using stdio transport."""
    mcp_server.run()


if __name__ == "__main__":
    run_server()
