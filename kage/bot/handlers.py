"""Telegram bot message, command, and callback query handlers with tool calling."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from kage.bot.middlewares import restricted
from kage.config import settings
from kage.llm.base import ChatMessage, ToolCall
from kage.llm.factory import get_llm
from kage.llm.prompt import get_system_prompt
from kage.mcp.client import mcp_client
# Ensure all tool modules are imported and registered
import kage.tools  # noqa: F401

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
        f"• MCP Server: `FastMCP (11 tools connected via MCP client)`\n\n"
        f"Try commands like:\n"
        f"• *\"Add a task: Review PRs due tomorrow at 6pm\"*\n"
        f"• *\"Remind me to drink water in 10 minutes\"*\n"
        f"• *\"What tasks are due this week?\"*\n"
        f"• *\"Complete task #1\"*"
    )
    if update.effective_message:
        await update.effective_message.reply_text(welcome_text, parse_mode="Markdown")


@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = (
        "🤖 **Kage Command Center - Help**\n\n"
        "• `/start` - Check bot status and welcome greeting\n"
        "• `/brief` - Trigger your Morning Brief on demand\n"
        "• `/help` - Show this help message\n\n"
        "💬 **Example natural prompts:**\n"
        "• \"What's on my calendar today?\"\n"
        "• \"Do I have any urgent emails?\"\n"
        "• \"What GitHub notifications do I have?\"\n"
        "• \"Add a task to buy groceries tomorrow\"\n"
        "• \"Remind me to call John at 5pm today\"\n"
        "• \"What tasks are due this week?\"\n"
        "• \"Complete task 2\"\n"
        "• \"Delete task 3\" (requires confirmation)"
    )
    if update.effective_message:
        await update.effective_message.reply_text(help_text, parse_mode="Markdown")


@restricted
async def brief_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /brief command to generate morning brief on demand."""
    if not update.effective_message:
        return
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    
    from kage.scheduler.brief import fetch_brief_raw_data, generate_morning_brief_text
    data = fetch_brief_raw_data()
    brief_text = await generate_morning_brief_text(data)

    try:
        await update.effective_message.reply_text(brief_text, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(brief_text)


@restricted
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process user message through LLM with tool calling and confirmation support."""
    if not update.effective_message or not update.effective_message.text:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    user_text = update.effective_message.text

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # 1. Prepare initial conversation messages
    system_prompt = get_system_prompt()
    messages: List[ChatMessage] = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_text),
    ]

    llm = get_llm()
    tools_schema = await mcp_client.get_openai_tools()

    try:
        # 2. First LLM call with tools
        response = await llm.generate(messages=messages, tools=tools_schema)

        # 3. If LLM wants to call tools, execute them via MCP
        if response.tool_calls:
            assistant_msg = ChatMessage(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            )
            messages.append(assistant_msg)

            for tc in response.tool_calls:
                # Check if tool requires explicit user confirmation
                if mcp_client.requires_confirmation(tc.name) and not tc.arguments.get("confirmed", False):
                    # Prompt user with inline confirmation buttons
                    action_summary = f"⚠️ *Confirmation Required*\n\nAction: `{tc.name}`\nArguments: `{json.dumps(tc.arguments)}`\n\nProceed?"
                    confirm_payload = f"cf:{tc.name}:{tc.arguments.get('task_id', 0)}"
                    cancel_payload = f"cl:{tc.name}:{tc.arguments.get('task_id', 0)}"
                    
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Confirm", callback_data=confirm_payload),
                            InlineKeyboardButton("❌ Cancel", callback_data=cancel_payload),
                        ]
                    ])
                    await update.effective_message.reply_text(
                        action_summary,
                        reply_markup=keyboard,
                        parse_mode="Markdown",
                    )
                    return

                # Execute tool via MCP client
                tool_result = await mcp_client.call_tool(
                    name=tc.name,
                    arguments=tc.arguments,
                    context={"user_id": user_id, "chat_id": chat_id},
                )

                messages.append(
                    ChatMessage(
                        role="tool",
                        content=json.dumps(tool_result),
                        tool_call_id=tc.id,
                    )
                )

            # Second LLM call to synthesize the result
            final_response = await llm.generate(messages=messages)
            reply_text = final_response.content or "Done."
        else:
            reply_text = response.content or "(No response)"

        try:
            await update.effective_message.reply_text(reply_text, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.effective_message.reply_text(f"⚠️ Error: {str(e)}")


@restricted
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmation buttons for side-effect actions."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    data = query.data.split(":")
    if len(data) < 3:
        return

    action_type, tool_name, item_id = data[0], data[1], data[2]

    if action_type == "cl":
        # Cancelled
        await query.edit_message_text(f"❌ Cancelled action `{tool_name}` for item #{item_id}.")
        return

    if action_type == "cf" and tool_name == "delete_task":
        # Confirmed deletion
        try:
            task_id = int(item_id)
            result = await mcp_client.call_tool(
                name="delete_task",
                arguments={"task_id": task_id, "confirmed": True},
            )
            msg = result.get("result", {}).get("message") or f"Task #{task_id} deleted."
            await query.edit_message_text(f"✅ {msg}")
        except Exception as e:
            await query.edit_message_text(f"⚠️ Failed to delete task: {e}")
