"""Google Calendar and Gmail read-only integration tools."""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any, Dict, List, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pydantic import BaseModel, Field

from kage.config import settings
from kage.tools.registry import registry

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def get_google_credentials() -> Optional[Credentials]:
    """Load and refresh valid Google OAuth credentials."""
    if not settings.google_token_file.exists():
        logger.warning(f"Google token file not found at {settings.google_token_file}")
        return None

    creds = Credentials.from_authorized_user_file(str(settings.google_token_file), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(settings.google_token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception as e:
            logger.error(f"Failed to refresh Google OAuth token: {e}")
            return None

    return creds if creds and creds.valid else None


# =====================================================================
# Argument Schemas
# =====================================================================

class ListCalendarEventsArgs(BaseModel):
    start_date: Optional[str] = Field(
        None,
        description="Start ISO-8601 date/time (defaults to start of today in Asia/Kolkata).",
    )
    end_date: Optional[str] = Field(
        None,
        description="End ISO-8601 date/time (defaults to end of today in Asia/Kolkata).",
    )
    max_results: int = Field(
        10,
        ge=1,
        le=50,
        description="Maximum number of events to fetch (1-50).",
    )


class ListUnreadEmailsArgs(BaseModel):
    max_results: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum number of unread emails to retrieve (1-20).",
    )
    query: str = Field(
        "is:unread label:INBOX",
        description="Gmail search query filter. Defaults to 'is:unread label:INBOX'.",
    )


# =====================================================================
# Tool Implementations (Strict Read-Only)
# =====================================================================

@registry.register(
    name="list_calendar_events",
    description="Fetch upcoming Google Calendar events for today or a specified date range. Read-only.",
    args_schema=ListCalendarEventsArgs,
)
def list_calendar_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 10,
) -> Dict[str, Any]:
    creds = get_google_credentials()
    if not creds:
        return {"error": "Google Calendar authentication token not available or expired."}

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    now = datetime.now(settings.tz)

    if not start_date:
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        time_min = start_dt.isoformat()
    else:
        time_min = start_date

    if not end_date:
        end_dt = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        time_max = end_dt.isoformat()
    else:
        time_max = end_date

    try:
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        items = events_result.get("items", [])

        events = []
        for item in items:
            start = item.get("start", {}).get("dateTime", item.get("start", {}).get("date"))
            end = item.get("end", {}).get("dateTime", item.get("end", {}).get("date"))
            summary = item.get("summary", "(No Title)")
            desc = (item.get("description") or "")[:200]
            location = item.get("location", "")

            events.append({
                "summary": summary,
                "start": start,
                "end": end,
                "location": location,
                "description_preview": desc,
            })

        return {
            "count": len(events),
            "events": events,
            "period": f"{time_min} to {time_max}",
        }
    except Exception as e:
        logger.error(f"Error fetching Google Calendar events: {e}", exc_info=True)
        return {"error": f"Calendar API error: {str(e)}"}


@registry.register(
    name="list_unread_emails",
    description="Fetch important unread emails from Gmail inbox with truncated previews. Read-only.",
    args_schema=ListUnreadEmailsArgs,
)
def list_unread_emails(max_results: int = 5, query: str = "is:unread label:INBOX") -> Dict[str, Any]:
    creds = get_google_credentials()
    if not creds:
        return {"error": "Gmail authentication token not available or expired."}

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    try:
        results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        messages = results.get("messages", [])

        emails = []
        for msg_meta in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_meta["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            subject = headers.get("Subject", "(No Subject)")
            sender = headers.get("From", "(Unknown Sender)")
            date_str = headers.get("Date", "")
            snippet = msg.get("snippet", "")[:250]  # Truncate to defend against prompt injection and bloat

            # Format with untrusted wrapper
            emails.append({
                "id": msg_meta["id"],
                "subject": subject,
                "sender": sender,
                "date": date_str,
                "snippet": f"[UNTRUSTED EMAIL CONTENT]: {snippet}",
            })

        return {
            "count": len(emails),
            "emails": emails,
        }
    except Exception as e:
        logger.error(f"Error fetching Gmail messages: {e}", exc_info=True)
        return {"error": f"Gmail API error: {str(e)}"}
