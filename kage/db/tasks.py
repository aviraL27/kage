"""Database repository operations for tasks and reminders."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from kage.config import settings
from kage.db.database import get_db_connection


def create_task(
    title: str,
    due_date: Optional[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    """Insert a new task into the database."""
    now_iso = datetime.now(settings.tz).isoformat()
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (title, description, due_date, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (title.strip(), description.strip(), due_date, now_iso),
        )
        task_id = cursor.lastrowid
        return {
            "id": task_id,
            "title": title.strip(),
            "description": description.strip(),
            "due_date": due_date,
            "status": "pending",
            "created_at": now_iso,
        }


def list_tasks(
    status: Optional[str] = None,
    period: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List tasks filtered by status and optional time period ('today', 'this_week', 'all')."""
    now = datetime.now(settings.tz)
    query = "SELECT id, title, description, due_date, status, created_at, completed_at FROM tasks WHERE 1=1"
    params: List[Any] = []

    if status and status.lower() != "all":
        query += " AND status = ?"
        params.append(status.lower())

    if period:
        p = period.lower()
        if p == "today":
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
            query += " AND due_date IS NOT NULL AND due_date >= ? AND due_date <= ?"
            params.extend([today_start, today_end])
        elif p == "this_week":
            week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0).isoformat()
            week_end = (now + timedelta(days=6 - now.weekday())).replace(hour=23, minute=59, second=59).isoformat()
            query += " AND due_date IS NOT NULL AND due_date >= ? AND due_date <= ?"
            params.extend([week_start, week_end])

    query += " ORDER BY due_date ASC, id ASC"

    with get_db_connection() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single task by ID."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def complete_task(task_id: int) -> Optional[Dict[str, Any]]:
    """Mark a task as completed."""
    now_iso = datetime.now(settings.tz).isoformat()
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE tasks
            SET status = 'completed', completed_at = ?
            WHERE id = ?
            """,
            (now_iso, task_id),
        )
        if cursor.rowcount == 0:
            return None
        cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_task(task_id: int) -> bool:
    """Delete a task and its associated reminders."""
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0


def create_reminder(
    remind_at: str,
    message: str,
    task_id: Optional[int] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert a reminder record into the database."""
    now_iso = datetime.now(settings.tz).isoformat()
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reminders (task_id, remind_at, message, status, job_id, created_at)
            VALUES (?, ?, ?, 'scheduled', ?, ?)
            """,
            (task_id, remind_at, message.strip(), job_id, now_iso),
        )
        reminder_id = cursor.lastrowid
        return {
            "id": reminder_id,
            "task_id": task_id,
            "remind_at": remind_at,
            "message": message.strip(),
            "status": "scheduled",
            "job_id": job_id,
            "created_at": now_iso,
        }


def update_reminder_status(reminder_id: int, status: str, job_id: Optional[str] = None) -> None:
    """Update reminder status and optional job ID."""
    with get_db_connection() as conn:
        if job_id:
            conn.execute(
                "UPDATE reminders SET status = ?, job_id = ? WHERE id = ?",
                (status, job_id, reminder_id),
            )
        else:
            conn.execute(
                "UPDATE reminders SET status = ? WHERE id = ?",
                (status, reminder_id),
            )


def list_reminders(status: Optional[str] = "scheduled") -> List[Dict[str, Any]]:
    """List reminders with optional status filter."""
    query = "SELECT * FROM reminders"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY remind_at ASC"

    with get_db_connection() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
