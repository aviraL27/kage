"""Telegram bot message, command, voice, and photo handlers with tool calling."""

from __future__ import annotations

import io
import json
import logging
from typing import Any, Dict, List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from kage.audio.transcription import transcribe_audio
from kage.audio.tts import synthesize_speech
from kage.bot.middlewares import restricted
from kage.config import settings
from kage.llm.base import ChatMessage, ToolCall
from kage.llm.factory import get_llm
from kage.llm.prompt import get_system_prompt
from kage.mcp.client import mcp_client
from kage.vision.analyzer import analyze_image
# Ensure all tool modules are imported and registered
import kage.tools  # noqa: F401

logger = logging.getLogger(__name__)


@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    welcome_text = (
        f"👋 Hello, {user.first_name if user else 'commander'}!\n\n"
        f"I am **Kage (影)**, your personal AI command center agent (J.A.R.V.I.S. Mode Active).\n\n"
        f"**Active Capabilities:**\n"
        f"• Multi-Inbox Gmail Engine (Search, Read Threads, Create Drafts)\n"
        f"• Voice In & Voice Out (Groq Whisper + Edge Neural Speech)\n"
        f"• Multimodal Vision (Send any image, note, or receipt)\n"
        f"• Live Web Search & Page Reader (DuckDuckGo + Jina Reader)\n"
        f"• Local PC Hardware Bridge (Lenovo LOQ / Windows 11)\n"
        f"• 7:30 AM Morning Brief & 9:30 PM Evening Debrief\n\n"
        f"Try commands like:\n"
        f"• 🎙️ *Send a voice note asking anything*\n"
        f"• 📷 *Send a photo with a caption*\n"
        f"• *\"Search emails for flight tickets across all accounts\"*\n"
        f"• *\"What is my PC battery and hardware status?\"*\n"
        f"• *\"Search the web for latest AI news\"*\n"
        f"• `/brief` (Morning brief) | `/debrief` (Evening reflection)"
    )
    if update.effective_message:
        await update.effective_message.reply_text(welcome_text, parse_mode="Markdown")


@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = (
        "🤖 **Kage J.A.R.V.I.S. Command Center - Help**\n\n"
        "• `/start` - Check bot status and welcome greeting\n"
        "• `/brief` - Trigger your Morning Brief on demand\n"
        "• `/debrief` - Trigger your Evening Reflection on demand\n"
        "• `/help` - Show this help message\n\n"
        "🎙️ **Voice Notes**: Send any audio message. Kage will transcribe and talk back in voice!\n"
        "📷 **Vision**: Send photos of notes, bills, or diagrams with questions.\n"
        "🌐 **Web Search**: Ask Kage to look up current news, facts, or summarize URLs.\n"
        "💻 **PC Control**: Ask for your Lenovo LOQ laptop status or to lock the workstation.\n"
        "📬 **Multi-Email**: Search or summarize across all your connected Google accounts."
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
async def debrief_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /debrief command to trigger evening reflection on demand."""
    if not update.effective_message:
        return
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    from kage.scheduler.debrief import fetch_evening_debrief_data, generate_evening_debrief_text
    data = fetch_evening_debrief_data()
    debrief_text = await generate_evening_debrief_text(data)

    try:
        await update.effective_message.reply_text(debrief_text, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(debrief_text)


async def execute_agent_pipeline(
    user_prompt: str,
    user_id: int,
    chat_id: int,
    update: Update,
) -> Optional[str]:
    """Execute LLM agent loop with MCP tools and confirmation handling."""
    system_prompt = get_system_prompt()
    messages: List[ChatMessage] = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    llm = get_llm()
    tools_schema = await mcp_client.get_openai_tools()

    # First LLM call
    response = await llm.generate(messages=messages, tools=tools_schema)

    # Process tool calls
    if response.tool_calls:
        assistant_msg = ChatMessage(
            role="assistant",
            content=response.content or "",
            tool_calls=response.tool_calls,
        )
        messages.append(assistant_msg)

        for tc in response.tool_calls:
            # Check if confirmation is required
            if mcp_client.requires_confirmation(tc.name) and not tc.arguments.get("confirmed", False):
                action_summary = f"⚠️ *Confirmation Required*\n\nAction: `{tc.name}`\nArguments: `{json.dumps(tc.arguments)}`\n\nProceed?"
                confirm_payload = f"cf:{tc.name}:{tc.arguments.get('task_id', 0)}"
                cancel_payload = f"cl:{tc.name}:{tc.arguments.get('task_id', 0)}"

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Confirm", callback_data=confirm_payload),
                        InlineKeyboardButton("❌ Cancel", callback_data=cancel_payload),
                    ]
                ])
                if update.effective_message:
                    await update.effective_message.reply_text(
                        action_summary,
                        reply_markup=keyboard,
                        parse_mode="Markdown",
                    )
                return None

            # Execute tool
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
        return final_response.content or "Done."
    else:
        return response.content or "(No response)"


@restricted
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process incoming text message through LLM agent."""
    if not update.effective_message or not update.effective_message.text:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    user_text = update.effective_message.text

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        reply_text = await execute_agent_pipeline(user_text, user_id, chat_id, update)
        if reply_text:
            try:
                await update.effective_message.reply_text(reply_text, parse_mode="Markdown")
            except Exception:
                await update.effective_message.reply_text(reply_text)
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.effective_message.reply_text(f"⚠️ Error: {str(e)}")


@restricted
async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice memo: transcribe with Groq Whisper, run agent, and talk back with edge-tts."""
    if not update.effective_message or not update.effective_message.voice:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    voice = update.effective_message.voice

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)

    try:
        # Download voice file
        voice_file = await context.bot.get_file(voice.file_id)
        voice_bytes = await voice_file.download_as_bytearray()

        # Transcribe with Groq Whisper
        transcription = await transcribe_audio(bytes(voice_bytes))
        if not transcription:
            await update.effective_message.reply_text("⚠️ Could not transcribe audio memo.")
            return

        logger.info(f"Transcribed voice memo from {user_id}: '{transcription}'")
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        # Run agent
        reply_text = await execute_agent_pipeline(transcription, user_id, chat_id, update)
        if not reply_text:
            return

        # Send text transcription acknowledgment + answer
        text_reply = f"🎙️ *\"{transcription}\"*\n\n{reply_text}"
        try:
            await update.effective_message.reply_text(text_reply, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(text_reply)

        # Synthesize voice reply
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)
        audio_reply = await synthesize_speech(reply_text)
        if audio_reply:
            voice_stream = io.BytesIO(audio_reply)
            voice_stream.name = "jarvis_response.mp3"
            await update.effective_message.reply_voice(voice=voice_stream)

    except Exception as e:
        logger.error(f"Error handling voice message: {e}", exc_info=True)
        await update.effective_message.reply_text(f"⚠️ Error processing voice memo: {str(e)}")


@restricted
async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photo: inspect with Groq Vision / Llama 3.2 Vision and run agent."""
    if not update.effective_message or not update.effective_message.photo:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    # Highest resolution photo is last in the list
    photo = update.effective_message.photo[-1]
    caption = update.effective_message.caption or "Analyze this image and describe all important data, tasks, and info."

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        # Download photo
        photo_file = await context.bot.get_file(photo.file_id)
        photo_bytes = await photo_file.download_as_bytearray()

        # Run vision inspection
        analysis = await analyze_image(bytes(photo_bytes), prompt=caption)

        # Combine into agent prompt
        agent_prompt = (
            f"[USER SHARED AN IMAGE]\n"
            f"Visual Analysis of Image:\n{analysis}\n\n"
            f"User's Caption / Intent: {caption}"
        )

        reply_text = await execute_agent_pipeline(agent_prompt, user_id, chat_id, update)
        if reply_text:
            try:
                await update.effective_message.reply_text(reply_text, parse_mode="Markdown")
            except Exception:
                await update.effective_message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Error handling photo message: {e}", exc_info=True)
        await update.effective_message.reply_text(f"⚠️ Error inspecting image: {str(e)}")


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
