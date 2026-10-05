"""Interactive script to authenticate with Google OAuth and generate token.json."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Read-only scopes for Google Calendar and Gmail
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"


def authenticate() -> Credentials:
    """Run Google OAuth 2.0 flow and persist token.json."""
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Missing credentials file at {CREDENTIALS_FILE}. "
            "Please ensure credentials.json exists."
        )

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired Google OAuth access token...", flush=True)
            creds.refresh(Request())
        else:
            print("Starting Google OAuth flow...", flush=True)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE),
                SCOPES,
            )
            # Run local server to capture the redirect
            creds = flow.run_local_server(
                port=0,
                prompt="consent",
                authorization_prompt_message="Please visit this URL to authorize this application: {url}",
                success_message="Authentication successful! You may now close this browser window.",
                open_browser=True,
            )

        with open(TOKEN_FILE, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
        print(f"Authentication successful! Token saved to {TOKEN_FILE}", flush=True)

    return creds


if __name__ == "__main__":
    authenticate()
