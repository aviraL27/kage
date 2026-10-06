"""Database repository for persistent memory (facts, preferences, settings)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from kage.config import settings
from kage.db.database import get_db_connection


def set_memory(key: str, value: str, category: str = "general") -> Dict[str, Any]:
    """Store or update a key-value memory."""
    now_iso = datetime.now(settings.tz).isoformat()
    cleaned_key = key.strip().lower()
    cleaned_val = value.strip()
    cleaned_cat = category.strip().lower()

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO memories (key, value, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                category = excluded.category,
                updated_at = excluded.updated_at
            """,
            (cleaned_key, cleaned_val, cleaned_cat, now_iso, now_iso),
        )
        return {
            "key": cleaned_key,
            "value": cleaned_val,
            "category": cleaned_cat,
            "updated_at": now_iso,
        }


def get_memory(key: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single memory by key."""
    cleaned_key = key.strip().lower()
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM memories WHERE key = ?", (cleaned_key,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_memory(key: str) -> bool:
    """Delete a memory by key."""
    cleaned_key = key.strip().lower()
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM memories WHERE key = ?", (cleaned_key,))
        return cursor.rowcount > 0


def list_memories(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all stored memories, optionally filtered by category."""
    query = "SELECT * FROM memories"
    params = []
    if category:
        query += " WHERE category = ?"
        params.append(category.strip().lower())
    query += " ORDER BY category ASC, key ASC"

    with get_db_connection() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_formatted_memories() -> str:
    """Format all stored memories into a prompt-ready bulleted list."""
    all_mems = list_memories()
    if not all_mems:
        return "(No persistent memories stored yet)"

    lines = []
    for m in all_mems:
        lines.append(f"• [{m['category'].upper()}] {m['key']}: {m['value']}")
    return "\n".join(lines)
