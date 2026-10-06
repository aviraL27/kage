"""Evening Reflection & Debrief job scheduled daily at 9:30 PM IST."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from kage.config import settings
from kage.db import tasks as db_tasks
from kage.llm.base import ChatMessage
from kage.llm.factory import get_llm
from kage.llm.prompt import get_system_prompt
from kage.scheduler.service import scheduler_service, _telegram_sender_hook
from kage.tools.google_tools import list_calendar_events

logger = logging.getLogger(__name__)


def fetch_evening_debrief_data() -> Dict[str, Any]:
    """Collect raw context for today's reflection and tomorrow's preview."""
    now = datetime.now(settings.tz)
    tomorrow = now + timedelta(days=1)

    # 1. Today's task accomplishments vs pending
    all_tasks = db_tasks.list_tasks(status="all")
    completed_today = [t for t in all_tasks if t.get("status") == "completed"]
    pending_tasks = [t for t in all_tasks if t.get("status") == "pending"]

    # 2. Tomorrow's calendar events preview
    tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
    cal_res = list_calendar_events(start_date=tomorrow_start, end_date=tomorrow_end, max_results=10)
    tomorrow_events = cal_res.get("events", []) if "error" not in cal_res else []

    return {
        "date_str": now.strftime("%A, %B %d, %Y"),
        "tomorrow_str": tomorrow.strftime("%A, %B %d"),
        "completed_tasks": completed_today,
        "pending_tasks": pending_tasks,
        "tomorrow_events": tomorrow_events,
    }


async def generate_evening_debrief_text(data: Optional[Dict[str, Any]] = None) -> str:
    """Use the LLM to compose a thoughtful, concise evening reflection."""
    if data is None:
        data = fetch_evening_debrief_data()

    system_prompt = get_system_prompt()
    user_prompt = f"""Generate my Evening Debrief & Reflection for tonight ({data['date_str']}).

RAW PROGRESS & SCHEDULE DATA:
1. Tasks Completed:
{data['completed_tasks']}

2. Remaining Pending Tasks:
{data['pending_tasks']}

3. Tomorrow's Schedule Preview ({data['tomorrow_str']}):
{data['tomorrow_events']}

FORMAT & PERSONA:
- Persona: J.A.R.V.I.S., loyal, refined, motivating.
- Acknowledge achievements completed today.
- Highlight unfinished items with gentle recommendations on whether to rollover or tackle tomorrow.
- Preview tomorrow's morning schedule.
- Keep it under 250 words, clean markdown bullets.
"""

    llm = get_llm()
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    response = await llm.generate(messages=messages)
    return response.content or "Evening debrief generated. Rest well, sir."


async def send_evening_debrief_job() -> None:
    """Scheduled task executed at 9:30 PM IST every evening."""
    logger.info("Executing scheduled Evening Debrief job...")
    if not settings.allowed_user_ids:
        logger.warning("No allowed_user_ids configured. Skipping evening debrief broadcast.")
        return

    hook = scheduler_service.get_telegram_sender_hook()
    if not hook:
        logger.warning("Telegram sender hook not registered. Cannot dispatch debrief.")
        return

    data = fetch_evening_debrief_data()
    debrief_text = await generate_evening_debrief_text(data)

    for user_id in settings.allowed_user_ids:
        try:
            await hook(user_id, debrief_text)
            logger.info(f"Delivered evening debrief to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to deliver evening debrief to {user_id}: {e}")


def schedule_evening_debrief_cron() -> None:
    """Register the recurring 9:30 PM IST debrief cron job with APScheduler."""
    job_id = "daily_evening_debrief_job"
    existing = scheduler_service.scheduler.get_job(job_id)
    if existing:
        logger.info(f"Evening debrief cron job '{job_id}' already registered.")
        return

    scheduler_service.add_cron_job(
        func=send_evening_debrief_job,
        job_id=job_id,
        hour=21,
        minute=30,
        replace_existing=True,
    )
    logger.info("Scheduled recurring 9:30 PM IST Evening Debrief job in APScheduler.")
