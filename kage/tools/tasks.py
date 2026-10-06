"""Task and reminder tools with strict Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from kage.config import settings
from kage.db import tasks as db_tasks
from kage.scheduler.service import scheduler_service
from kage.tools.registry import registry


# =====================================================================
# Argument Schemas
# =====================================================================

class AddTaskArgs(BaseModel):
    title: str = Field(..., description="Clear title or summary of the task to be done.")
    due_date: Optional[str] = Field(
        None,
        description="Optional due date/time in ISO-8601 format (e.g. '2026-10-06T18:00:00+05:30') in Asia/Kolkata timezone.",
    )
    description: Optional[str] = Field(
        "",
        description="Optional additional details, context, or notes for the task.",
    )


class ListTasksArgs(BaseModel):
    status: Optional[str] = Field(
        "pending",
        description="Status filter: 'pending', 'completed', or 'all'. Defaults to 'pending'.",
    )
    period: Optional[str] = Field(
        None,
        description="Optional period filter: 'today', 'this_week', or None for all.",
    )


class CompleteTaskArgs(BaseModel):
    task_id: int = Field(..., description="The numeric ID of the task to complete.")


class SetReminderArgs(BaseModel):
    message: str = Field(..., description="The message or alert to send when the reminder triggers.")
    remind_at: str = Field(
        ...,
        description="Exact date and time to fire the reminder in ISO-8601 format (e.g. '2026-10-06T18:00:00+05:30') in Asia/Kolkata timezone.",
    )
    task_id: Optional[int] = Field(
        None,
        description="Optional task ID associated with this reminder.",
    )


class DeleteTaskArgs(BaseModel):
    task_id: int = Field(..., description="The numeric ID of the task to delete.")
    confirmed: bool = Field(
        False,
        description="Explicit user confirmation flag. Must be true to delete.",
    )


# =====================================================================
# Tool Implementations
# =====================================================================

@registry.register(
    name="add_task",
    description="Create a new task on the user's task list with an optional due date.",
    args_schema=AddTaskArgs,
)
def add_task(title: str, due_date: Optional[str] = None, description: str = "") -> Dict[str, Any]:
    task = db_tasks.create_task(title=title, due_date=due_date, description=description)
    return {
        "message": f"Task #{task['id']} created: '{task['title']}'",
        "task": task,
    }


@registry.register(
    name="list_tasks",
    description="List tasks from the database filtered by status ('pending', 'completed', 'all') and period ('today', 'this_week').",
    args_schema=ListTasksArgs,
)
def list_tasks(status: Optional[str] = "pending", period: Optional[str] = None) -> Dict[str, Any]:
    tasks = db_tasks.list_tasks(status=status, period=period)
    return {
        "count": len(tasks),
        "tasks": tasks,
    }


@registry.register(
    name="complete_task",
    description="Mark a task as completed given its numeric ID.",
    args_schema=CompleteTaskArgs,
)
def complete_task(task_id: int) -> Dict[str, Any]:
    task = db_tasks.complete_task(task_id=task_id)
    if not task:
        return {"error": f"Task #{task_id} not found."}
    return {
        "message": f"Task #{task_id} marked as completed: '{task['title']}'",
        "task": task,
    }


@registry.register(
    name="set_reminder",
    description="Schedule a persistent alert/reminder that will notify the user on Telegram at a specified ISO-8601 time.",
    args_schema=SetReminderArgs,
)
def set_reminder(
    message: str,
    remind_at: str,
    task_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    user_id = context.get("user_id") if context else None

    # Parse ISO-8601 date string
    try:
        dt = datetime.fromisoformat(remind_at)
    except ValueError:
        return {"error": f"Invalid ISO-8601 format for remind_at: '{remind_at}'."}

    # Ensure datetime is in Asia/Kolkata
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
        user_id=user_id,
        task_id=task_id,
    )
    return {
        "message": f"Reminder scheduled for {dt.strftime('%A, %b %d %I:%M %p')}: '{message}'",
        "reminder": reminder,
    }


@registry.register(
    name="delete_task",
    description="Delete a task by its numeric ID. Always invoke this tool when the user asks to delete or remove a task; confirmation is handled by the system.",
    args_schema=DeleteTaskArgs,
    requires_confirmation=True,
)
def delete_task(task_id: int, confirmed: bool = False) -> Dict[str, Any]:
    task = db_tasks.get_task(task_id)
    if not task:
        return {"error": f"Task #{task_id} not found."}

    if not confirmed:
        # Prompt for confirmation
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
