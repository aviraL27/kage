"""APScheduler service with SQLite persistent job store."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from kage.config import settings
from kage.db.tasks import create_reminder, update_reminder_status

logger = logging.getLogger(__name__)

# Global reference to Telegram notification sender callback
_telegram_sender_hook: Optional[Callable[[int, str], Any]] = None
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Register the main application event loop for cross-thread async dispatch."""
    global _main_loop
    _main_loop = loop


def set_telegram_sender_hook(hook: Callable[[int, str], Any]) -> None:
    """Set hook for sending Telegram notifications when reminders trigger."""
    global _telegram_sender_hook
    _telegram_sender_hook = hook


def reminder_job_runner(reminder_id: int, message: str, user_id: int) -> None:
    """Module-level job function executed when a reminder triggers."""
    logger.info(f"Reminder triggered: id={reminder_id}, message='{message}', user_id={user_id}")
    try:
        update_reminder_status(reminder_id, "fired")
    except Exception as e:
        logger.error(f"Error updating reminder status: {e}")

    # Dispatch to Telegram if hook is configured
    if _telegram_sender_hook:
        formatted_text = f"🔔 *Reminder:*\n{message}"
        try:
            res = _telegram_sender_hook(user_id, formatted_text)
            if asyncio.iscoroutine(res):
                if _main_loop and _main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(res, _main_loop)
                else:
                    asyncio.run(res)
        except Exception as e:
            logger.error(f"Error dispatching reminder to Telegram: {e}")


class SchedulerService:
    """Manages the persistent APScheduler instance with SQLite storage."""

    def __init__(self) -> None:
        # Use SQLite persistent job store
        jobstore_url = f"sqlite:///{settings.jobs_database_path.resolve().as_posix()}"
        jobstores = {
            "default": SQLAlchemyJobStore(url=jobstore_url)
        }
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone=settings.tz,
        )

    def start(self) -> None:
        """Start the scheduler if not already running."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("APScheduler service started with SQLite persistent job store.")

    def shutdown(self) -> None:
        """Shut down the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler service shut down.")

    def schedule_reminder(
        self,
        remind_at: datetime,
        message: str,
        user_id: Optional[int] = None,
        task_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Schedule a persistent reminder job."""
        target_user = user_id or (list(settings.allowed_user_ids)[0] if settings.allowed_user_ids else 0)

        # Ensure datetime is localized to Asia/Kolkata
        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(tzinfo=settings.tz)
        else:
            remind_at = remind_at.astimezone(settings.tz)

        remind_at_iso = remind_at.isoformat()
        
        # 1. Create DB entry first
        reminder_record = create_reminder(
            remind_at=remind_at_iso,
            message=message,
            task_id=task_id,
        )
        reminder_id = reminder_record["id"]
        job_id = f"reminder_{reminder_id}"

        # 2. Add job to APScheduler
        self.scheduler.add_job(
            reminder_job_runner,
            "date",
            run_date=remind_at,
            args=[reminder_id, message, target_user],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # 3. Update DB record with job_id
        update_reminder_status(reminder_id, "scheduled", job_id=job_id)
        reminder_record["job_id"] = job_id

        logger.info(f"Scheduled reminder {reminder_id} for {remind_at_iso} (job {job_id})")
        return reminder_record


# Singleton scheduler service
scheduler_service = SchedulerService()
