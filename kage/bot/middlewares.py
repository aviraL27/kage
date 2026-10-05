"""Security and authorization middlewares for Telegram updates."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Coroutine
from telegram import Update
from telegram.ext import ContextTypes

from kage.config import settings

logger = logging.getLogger(__name__)


def restricted(
    func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
    """Decorator to enforce Telegram user ID allowlist.
    
    Unauthorized requests are dropped silently to avoid leaking bot state or confirming existence.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not user:
            return

        if not settings.is_user_allowed(user.id):
            logger.warning(
                f"Unauthorized access attempt blocked: user_id={user.id}, "
                f"username={user.username}, full_name={user.full_name}"
            )
            # Silently drop unauthorized attempts for security
            return

        return await func(update, context)

    return wrapper
