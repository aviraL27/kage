"""Telegram bot message and command handlers."""

from __future__ import annotations

import logging
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from kage.bot.middlewares import restricted
from kage.config import settings
from kage.llm.base import ChatMessage
from kage.llm.factory import get_llm
from kage.llm.prompt import get_system_prompt

logger = logging.getLogger(__name__)


@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    welcome_text = (
        f"👋 Hello, {user.first_name if user else 'commander'}!\n\n"
        f"I am **Kage (影)**, your personal command center agent.\n\n"
        f"**Active Configuration:**\n"
        f"• Timezone: `{settings.timezone_name}`\n"
        f"• LLM Provider: `{settings.llm_provider}`\n"
        f"• Security: Allowlist Active (User ID `{user.id if user else 'unknown'}`)\n\n"
        f"You can talk to me directly, ask questions, or issue commands."
    )
    if update.effective_message:
        await update.effective_message.reply_text(welcome_text, parse_mode="Markdown")


@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = (
        "🤖 **Kage Command Center - Help**\n\n"
        "• `/start` - Check bot status and welcome greeting\n"
        "• `/help` - Show this help message\n\n"
        "💬 Or simply send me any message, e.g.:\n"
        "  - \"Hello Kage, who are you?\"\n"
        "  - \"What is today's date and time?\""
    )
    if update.effective_message:
        await update.effective_message.reply_text(help_text, parse_mode="Markdown")


@restricted
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pass user message to LLM adapter and reply."""
    if not update.effective_message or not update.effective_message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.effective_message.text

    # Send typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # Prepare prompt with dynamic IST context
    system_prompt = get_system_prompt()
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_text),
    ]

    llm = get_llm()
    try:
        response = await llm.generate(messages=messages)
        reply_content = response.content or "(No response generated)"

        # Attempt to reply with Markdown, fallback to raw text if parsing fails
        try:
            await update.effective_message.reply_text(reply_content, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(reply_content)

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.effective_message.reply_text(
            f"⚠️ An error occurred while generating response: {str(e)}"
        )
