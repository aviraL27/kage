"""Main entrypoint for Kage Telegram Bot."""

from __future__ import annotations

import logging
import sys
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from kage.bot.handlers import handle_message, help_command, start_command
from kage.config import settings

# Setup standard logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("kage")


def build_application() -> Application:
    """Build and configure the Telegram application."""
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not configured.")

    app = Application.builder().token(settings.telegram_bot_token).build()

    # Register command and message handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


def main() -> None:
    """Run the bot in polling mode."""
    logger.info("Initializing Kage Telegram Bot...")
    logger.info(f"Allowed User IDs: {settings.allowed_user_ids}")
    logger.info(f"Timezone: {settings.timezone_name}")
    logger.info(f"LLM Provider: {settings.llm_provider}")

    app = build_application()
    logger.info("Kage is listening for updates. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
