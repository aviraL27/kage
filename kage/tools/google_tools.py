"""Google Calendar and multi-account Gmail integration tools."""

from __future__ import annotations

import base64
import html
import logging
import re
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
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
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


# =====================================================================
# Multi-Account Credentials Helpers
# =====================================================================

def get_all_google_credentials() -> Dict[str, Credentials]:
    """Load all authorized Google OAuth credentials from tokens directory and fallback token.json."""
    creds_map: Dict[str, Credentials] = {}

    # 1. Check tokens directory for multi-account tokens
    if settings.tokens_dir.exists():
        for token_file in settings.tokens_dir.glob("*.json"):
            account_name = token_file.stem
            try:
                creds = Credentials.from_authorized_user_file(str(token_file))
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    token_file.write_text(creds.to_json(), encoding="utf-8")
                if creds and creds.valid:
                    creds_map[account_name] = creds
            except Exception as e:
                logger.error(f"Error loading credentials from {token_file}: {e}")

    # 2. Fallback to single root token.json if no tokens found in tokens_dir
    if not creds_map and settings.google_token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(settings.google_token_file))
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                settings.google_token_file.write_text(creds.to_json(), encoding="utf-8")
            if creds and creds.valid:
                creds_map["primary"] = creds
        except Exception as e:
            logger.error(f"Error loading credentials from {settings.google_token_file}: {e}")

    return creds_map


def get_google_credentials(account: Optional[str] = None) -> Optional[Credentials]:
    """Retrieve credentials for a specific account or default primary account."""
    all_creds = get_all_google_credentials()
    if not all_creds:
        return None

    if not account or account.lower() in ("primary", "all", "default"):
        # Look for primary account aviral.5015.xo or fallback to first
        for acc_name, creds in all_creds.items():
            if "aviral.5015.xo" in acc_name:
                return creds
        return next(iter(all_creds.values()))

    # Fuzzy match by substring or alias
    account_lower = account.lower()
    for acc_name, creds in all_creds.items():
        if account_lower in acc_name.lower():
            return creds

    return None


def _clean_body_text(text: str) -> str:
    """Clean and strip markup/extra whitespace from email text."""
    # Strip HTML tags
    cleaned = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<script[\s\S]*?</script>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    # Collapse excess whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip()


def _extract_email_payload(payload: dict) -> str:
    """Extract plain text or HTML body from a nested Gmail message payload."""
    parts = payload.get("parts", [])
    if parts:
        # First try text/plain
        for part in parts:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data")
                if data:
                    try:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    except Exception:
                        pass
            elif "parts" in part:
                sub_body = _extract_email_payload(part)
                if sub_body:
                    return sub_body

        # Fallback to text/html
        for part in parts:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data")
                if data:
                    try:
                        raw_html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                        return _clean_body_text(raw_html)
                    except Exception:
                        pass

    # No multipart, direct body
    data = payload.get("body", {}).get("data")
    if data:
        try:
            raw = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            if payload.get("mimeType") == "text/html":
                return _clean_body_text(raw)
            return raw
        except Exception:
            pass

    return ""


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
    account: Optional[str] = Field(
        None,
        description="Optional email account name or substring to check. Defaults to primary account.",
    )


class ListUnreadEmailsArgs(BaseModel):
    max_results: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum number of unread emails to retrieve per account (1-20).",
    )
    query: str = Field(
        "is:unread label:INBOX",
        description="Gmail search query filter. Defaults to 'is:unread label:INBOX'.",
    )
    account: Optional[str] = Field(
        "all",
        description="Specific account email/alias, or 'all' to check across all connected inboxes.",
    )


class SearchEmailsArgs(BaseModel):
    query: str = Field(
        ...,
        description="Gmail search query (e.g. 'from:google', 'subject:invoice', 'has:attachment', 'after:2026/01/01').",
    )
    max_results: int = Field(
        10,
        ge=1,
        le=30,
        description="Maximum number of matching emails to retrieve (1-30).",
    )
    account: Optional[str] = Field(
        "all",
        description="Specific account email/alias, or 'all' to search across all connected inboxes.",
    )


class ReadEmailThreadArgs(BaseModel):
    message_id: str = Field(
        ...,
        description="The unique Gmail message ID to read in full.",
    )
    account: Optional[str] = Field(
        None,
        description="Optional account email/alias holding the message. If omitted, all accounts are searched.",
    )


class CreateEmailDraftArgs(BaseModel):
    to: str = Field(
        ...,
        description="Recipient email address (e.g. 'colleague@example.com').",
    )
    subject: str = Field(
        ...,
        description="Subject line for the email draft.",
    )
    body: str = Field(
        ...,
        description="Body text for the email draft.",
    )
    account: Optional[str] = Field(
        None,
        description="Optional sender account email/alias to create the draft in. Defaults to primary account.",
    )


# =====================================================================
# Tool Implementations
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
    account: Optional[str] = None,
) -> Dict[str, Any]:
    creds = get_google_credentials(account)
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
    description="Fetch important unread emails from Gmail inbox with truncated previews across accounts. Read-only.",
    args_schema=ListUnreadEmailsArgs,
)
def list_unread_emails(
    max_results: int = 5,
    query: str = "is:unread label:INBOX",
    account: Optional[str] = "all",
) -> Dict[str, Any]:
    all_creds = get_all_google_credentials()
    if not all_creds:
        return {"error": "Gmail authentication tokens not available or expired."}

    # Determine which accounts to query
    target_accounts: Dict[str, Credentials] = {}
    if not account or account.lower() == "all":
        target_accounts = all_creds
    else:
        acc_creds = get_google_credentials(account)
        if acc_creds:
            target_accounts = {account: acc_creds}
        else:
            return {"error": f"Account '{account}' not found among connected inboxes ({list(all_creds.keys())})."}

    total_emails = []
    accounts_checked = []

    for acc_name, creds in target_accounts.items():
        accounts_checked.append(acc_name)
        try:
            service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
            messages = results.get("messages", [])

            for msg_meta in messages:
                msg = service.users().messages().get(
                    userId="me", id=msg_meta["id"], format="metadata",
                    metadataHeaders=["Subject", "From", "Date"]
                ).execute()

                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                subject = headers.get("Subject", "(No Subject)")
                sender = headers.get("From", "(Unknown Sender)")
                date_str = headers.get("Date", "")
                snippet = msg.get("snippet", "")[:250]

                total_emails.append({
                    "id": msg_meta["id"],
                    "account": acc_name,
                    "subject": subject,
                    "sender": sender,
                    "date": date_str,
                    "snippet": f"[UNTRUSTED EMAIL CONTENT]: {snippet}",
                })
        except Exception as e:
            logger.error(f"Error fetching unread emails for {acc_name}: {e}")

    return {
        "count": len(total_emails),
        "emails": total_emails,
        "accounts_checked": accounts_checked,
    }


@registry.register(
    name="search_emails",
    description="Search emails across all folders and accounts with full Gmail query syntax. Read-only.",
    args_schema=SearchEmailsArgs,
)
def search_emails(
    query: str,
    max_results: int = 10,
    account: Optional[str] = "all",
) -> Dict[str, Any]:
    all_creds = get_all_google_credentials()
    if not all_creds:
        return {"error": "Gmail authentication tokens not available or expired."}

    target_accounts: Dict[str, Credentials] = {}
    if not account or account.lower() == "all":
        target_accounts = all_creds
    else:
        acc_creds = get_google_credentials(account)
        if acc_creds:
            target_accounts = {account: acc_creds}
        else:
            return {"error": f"Account '{account}' not found among connected inboxes ({list(all_creds.keys())})."}

    matched_emails = []
    for acc_name, creds in target_accounts.items():
        try:
            service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
            messages = results.get("messages", [])

            for msg_meta in messages:
                msg = service.users().messages().get(
                    userId="me", id=msg_meta["id"], format="metadata",
                    metadataHeaders=["Subject", "From", "Date"]
                ).execute()

                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                matched_emails.append({
                    "id": msg_meta["id"],
                    "account": acc_name,
                    "subject": headers.get("Subject", "(No Subject)"),
                    "sender": headers.get("From", "(Unknown Sender)"),
                    "date": headers.get("Date", ""),
                    "snippet": f"[UNTRUSTED EMAIL CONTENT]: {msg.get('snippet', '')[:200]}",
                })
        except Exception as e:
            logger.error(f"Search failed on account {acc_name}: {e}")

    return {
        "count": len(matched_emails),
        "query": query,
        "emails": matched_emails,
    }


@registry.register(
    name="read_email_thread",
    description="Fetch and read the full text content of a specific email message ID. Read-only.",
    args_schema=ReadEmailThreadArgs,
)
def read_email_thread(
    message_id: str,
    account: Optional[str] = None,
) -> Dict[str, Any]:
    all_creds = get_all_google_credentials()
    if not all_creds:
        return {"error": "Gmail authentication tokens not available."}

    target_accounts = all_creds
    if account:
        matched = get_google_credentials(account)
        if matched:
            target_accounts = {account: matched}

    for acc_name, creds in target_accounts.items():
        try:
            service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
            if not msg:
                continue

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            raw_body = _extract_email_payload(msg.get("payload", {}))
            body_text = _clean_body_text(raw_body)
            # Truncate to 2000 chars to protect LLM context
            body_preview = body_text[:2000]

            return {
                "id": message_id,
                "account": acc_name,
                "subject": headers.get("Subject", "(No Subject)"),
                "sender": headers.get("From", "(Unknown Sender)"),
                "to": headers.get("To", ""),
                "date": headers.get("Date", ""),
                "body": f"[UNTRUSTED EMAIL CONTENT]:\n{body_preview}",
            }
        except Exception:
            continue

    return {"error": f"Email with ID '{message_id}' could not be found in authorized accounts."}


@registry.register(
    name="create_email_draft",
    description="Create an email draft in Gmail for review before sending.",
    args_schema=CreateEmailDraftArgs,
)
def create_email_draft(
    to: str,
    subject: str,
    body: str,
    account: Optional[str] = None,
) -> Dict[str, Any]:
    creds = get_google_credentials(account)
    if not creds:
        return {"error": "Google credentials not found for draft creation."}

    account_name = account or "primary"
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg["To"] = to
        msg["Subject"] = subject

        encoded_raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        draft = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": encoded_raw}},
        ).execute()

        return {
            "success": True,
            "draft_id": draft.get("id"),
            "account": account_name,
            "to": to,
            "subject": subject,
            "message": f"Successfully created email draft in Gmail ({account_name}) to {to}.",
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error creating Gmail draft: {e}", exc_info=True)
        if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
            return {
                "error": "Insufficient Gmail permissions to create drafts. Please authenticate with python scripts/auth_google.py to grant write/draft scope."
            }
        return {"error": f"Failed to create draft: {error_msg}"}
