"""Audit logging for all tool executions."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from kage.config import settings, BASE_DIR
from kage.db.database import get_db_connection

# Set up tool calls log file
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TOOL_LOG_FILE = LOGS_DIR / "tool_calls.log"

file_logger = logging.getLogger("kage.tool_audit")
file_logger.setLevel(logging.INFO)
if not file_logger.handlers:
    fh = logging.FileHandler(TOOL_LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    file_logger.addHandler(fh)


def log_tool_execution(
    tool_name: str,
    args: Dict[str, Any],
    result_summary: str,
    latency_ms: float,
    status: str = "success",
) -> None:
    """Record tool invocation details into both SQLite and the tool log file."""
    now_iso = datetime.now(settings.tz).isoformat()
    args_json = json.dumps(args, default=str)

    # 1. Write to audit file
    log_line = (
        f"tool={tool_name} | status={status} | latency={latency_ms:.2f}ms | "
        f"args={args_json} | result={result_summary}"
    )
    file_logger.info(log_line)

    # 2. Write to SQLite audit table
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO tool_audit_logs (timestamp, tool_name, args_json, result_summary, latency_ms, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now_iso, tool_name, args_json, result_summary, latency_ms, status),
            )
    except Exception as e:
        file_logger.error(f"Failed to write tool audit log to SQLite: {e}")
