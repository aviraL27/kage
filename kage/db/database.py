"""SQLite database connection and schema management."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Generator
from kage.config import settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    remind_at TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    job_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    args_json TEXT NOT NULL,
    result_summary TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);
CREATE INDEX IF NOT EXISTS idx_reminders_remind_at ON reminders(remind_at);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON tool_audit_logs(timestamp);
"""


def init_db() -> None:
    """Initialize database tables and indexes."""
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.database_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Provide a transactional database connection."""
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
