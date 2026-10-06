"""Interactive script to authenticate multiple Google accounts for Kage."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Scopes for Calendar read-only, Gmail read/search/draft (modify), and user identity
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKENS_DIR = BASE_DIR / "tokens"
PRIMARY_TOKEN_FILE = BASE_DIR / "token.json"


def list_authorized_accounts() -> list[str]:
    """Return a list of all currently authorized email accounts."""
    if not TOKENS_DIR.exists():
        return []
    return [p.stem for p in TOKENS_DIR.glob("*.json")]


def authenticate_account(account_hint: str | None = None) -> Credentials:
    """Run Google OAuth 2.0 flow, determine the authenticated email, and save to tokens/{email}.json."""
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Missing credentials file at {CREDENTIALS_FILE}. "
            "Please ensure credentials.json exists."
        )

    TOKENS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    if account_hint:
        print(f"🔑 Starting Google OAuth flow for: {account_hint}")
    else:
        print("🔑 Starting Google OAuth flow...")
    print("=" * 60)
    print("A browser window will open. Please log into the desired Google account and grant permissions.\n")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        SCOPES,
    )

    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        authorization_prompt_message="Please visit this URL to authorize this application: {url}",
        success_message="Authentication successful! You may now close this browser window and return to the terminal.",
        open_browser=True,
    )

    # Detect the email address of the account that just authenticated
    email = None
    try:
        oauth2_service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        user_info = oauth2_service.userinfo().get().execute()
        email = user_info.get("email")
    except Exception as e:
        print(f"⚠️ Could not automatically detect email address ({e}). Falling back to hint or manual input.")
        if account_hint:
            email = account_hint
        else:
            email = input("Please enter the email address you just signed in with: ").strip()

    if not email:
        email = "default_account"

    # Save to tokens/<email>.json
    token_path = TOKENS_DIR / f"{email}.json"
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    # Also keep root token.json updated if primary
    if not PRIMARY_TOKEN_FILE.exists():
        with open(PRIMARY_TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    print("\n" + "✅ " * 15)
    print(f"Successfully authenticated account: {email}")
    print(f"Token saved to: {token_path}")
    print("✅ " * 15 + "\n")

    return creds


def main() -> None:
    parser = argparse.ArgumentParser(description="Authenticate Google accounts for Kage.")
    parser.add_argument("--list", action="store_true", help="List all currently authorized accounts.")
    parser.add_argument("--account", type=str, default=None, help="Email or alias to authenticate.")
    args = parser.parse_args()

    if args.list:
        accounts = list_authorized_accounts()
        print("\n📋 Currently Authorized Google Accounts in Kage:")
        if accounts:
            for i, acc in enumerate(accounts, 1):
                print(f"  {i}. {acc}")
        else:
            print("  (No accounts authorized yet in tokens/)")
        print()
        return

    # Authenticate
    authenticate_account(args.account)

    # Show updated list
    accounts = list_authorized_accounts()
    print("📋 Currently Connected Inboxes in Kage:")
    for i, acc in enumerate(accounts, 1):
        print(f"  {i}. {acc}")
    print("\nTo add another account, simply run: python scripts/auth_google.py\n")


if __name__ == "__main__":
    main()
