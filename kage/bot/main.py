"""Main entrypoint for Kage Telegram Bot."""

from __future__ import annotations

import logging
import sys
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from kage.bot.handlers import handle_callback_query, handle_message, help_command, start_command
from kage.config import settings
from kage.db.database import init_db
from kage.scheduler.service import scheduler_service, set_telegram_sender_hook

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

    # Initialize SQLite database
    init_db()

    app = Application.builder().token(settings.telegram_bot_token).build()

    # Configure Telegram dispatch hook for scheduler reminders
    async def send_telegram_alert(user_id: int, text: str) -> None:
        try:
            await app.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send scheduled message to {user_id}: {e}")

    set_telegram_sender_hook(send_telegram_alert)

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors caused by Updates."""
        logger.warning(f"Telegram polling warning: {context.error}")

    app.add_error_handler(error_handler)

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


def main() -> None:
    """Run the bot and scheduler service."""
    logger.info("Initializing Kage Telegram Bot...")
    logger.info(f"Allowed User IDs: {settings.allowed_user_ids}")
    logger.info(f"Timezone: {settings.timezone_name}")
    logger.info(f"LLM Provider: {settings.llm_provider}")

    # Start APScheduler
    scheduler_service.start()

    app = build_application()
    logger.info("Kage is listening for updates. Press Ctrl+C to stop.")
    try:
        app.run_polling()
    finally:
        scheduler_service.shutdown()


if __name__ == "__main__":
    main()
