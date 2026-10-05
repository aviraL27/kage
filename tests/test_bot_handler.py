"""End-to-end test for bot handlers."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Update, User, Chat, Message

from kage.bot.handlers import handle_message, start_command
from kage.config import settings


@pytest.mark.asyncio
async def test_start_command_reply():
    """Verify /start handler replies with welcome message."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = 1487439060
    user.first_name = "Aviral"
    update.effective_user = user

    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    update.effective_message = message

    context = MagicMock()
    await start_command(update, context)

    message.reply_text.assert_called_once()
    reply_arg = message.reply_text.call_args[0][0]
    assert "Kage" in reply_arg
    assert "Aviral" in reply_arg


@pytest.mark.asyncio
async def test_handle_message_reply():
    """Verify message handler routes to Groq and replies."""
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = 1487439060
    update.effective_user = user

    chat = MagicMock(spec=Chat)
    chat.id = 1487439060
    update.effective_chat = chat

    message = MagicMock(spec=Message)
    message.text = "Hello! Please reply with 'SYSTEM READY' only."
    message.reply_text = AsyncMock()
    update.effective_message = message

    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()

    await handle_message(update, context)

    # Should send typing action
    context.bot.send_chat_action.assert_called_once()
    # Should reply to user
    message.reply_text.assert_called_once()
    reply_text = message.reply_text.call_args[0][0]
    assert len(reply_text) > 0
