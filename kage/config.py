"""Configuration management for Kage."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Set
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if present
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

        # Parse comma-separated list of allowed user IDs
        raw_ids = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
        self.allowed_user_ids: Set[int] = set()
        for item in raw_ids.split(","):
            cleaned = item.strip()
            if cleaned.isdigit() or (cleaned.startswith("-") and cleaned[1:].isdigit()):
                self.allowed_user_ids.add(int(cleaned))

        # Timezone settings
        self.timezone_name: str = os.getenv("TIMEZONE", "Asia/Kolkata").strip()
        try:
            self.tz: ZoneInfo = ZoneInfo(self.timezone_name)
        except Exception:
            self.tz = ZoneInfo("Asia/Kolkata")

        # LLM settings
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "groq").strip().lower()
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
        self.ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()

        # Storage paths
        self.database_path: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/kage.sqlite")
        self.jobs_database_path: Path = BASE_DIR / os.getenv("JOBS_DATABASE_PATH", "data/jobs.sqlite")

        # Google & GitHub integration
        self.google_credentials_file: Path = BASE_DIR / os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        self.google_token_file: Path = BASE_DIR / os.getenv("GOOGLE_TOKEN_FILE", "token.json")
        self.github_token: str = os.getenv("GITHUB_TOKEN", "").strip()

        # Ensure local data directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.jobs_database_path.parent.mkdir(parents=True, exist_ok=True)

    def is_user_allowed(self, user_id: int) -> bool:
        """Check if a given Telegram user ID is authorized."""
        return user_id in self.allowed_user_ids


# Global singleton instance
settings = Settings()
