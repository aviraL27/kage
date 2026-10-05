"""Tests for Telegram bot security and allowlist middleware."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Update, User

from kage.bot.middlewares import restricted
from kage.config import settings


@pytest.mark.asyncio
async def test_restricted_decorator_blocks_unauthorized_user():
    """Verify unauthorized users are blocked."""
    mock_handler = AsyncMock()
    decorated = restricted(mock_handler)

    # Fake update from unauthorized user
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 999999999  # Not allowed
    update.effective_user.username = "intruder"
    update.effective_user.full_name = "Intruder User"
    context = MagicMock()

    await decorated(update, context)

    # Handler must NOT have been called
    mock_handler.assert_not_called()


@pytest.mark.asyncio
async def test_restricted_decorator_allows_authorized_user():
    """Verify authorized users pass through."""
    mock_handler = AsyncMock()
    decorated = restricted(mock_handler)

    # Fake update from authorized user (1487439060 is in settings.allowed_user_ids)
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 1487439060
    update.effective_user.username = "aviral"
    update.effective_user.full_name = "Aviral"
    context = MagicMock()

    await decorated(update, context)

    # Handler MUST have been called
    mock_handler.assert_called_once_with(update, context)
