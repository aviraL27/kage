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
        self.tokens_dir: Path = BASE_DIR / "tokens"
        self.tokens_dir.mkdir(parents=True, exist_ok=True)
        self.github_token: str = os.getenv("GITHUB_TOKEN", "").strip()

        # Cloud deployment support: write credentials/tokens from environment variables if present
        # Multi-account tokens: GOOGLE_TOKENS_JSON can be a JSON object mapping email -> token JSON dict
        google_tokens_env = os.getenv("GOOGLE_TOKENS_JSON", "").strip()
        if google_tokens_env:
            try:
                import json
                tokens_dict = json.loads(google_tokens_env)
                if isinstance(tokens_dict, dict):
                    for email_key, token_val in tokens_dict.items():
                        target_file = self.tokens_dir / f"{email_key}.json"
                        token_str = json.dumps(token_val) if isinstance(token_val, dict) else str(token_val)
                        target_file.write_text(token_str, encoding="utf-8")
            except Exception:
                pass

        google_token_env = os.getenv("GOOGLE_TOKEN_JSON", "").strip()
        if google_token_env and not self.google_token_file.exists():
            self.google_token_file.parent.mkdir(parents=True, exist_ok=True)
            self.google_token_file.write_text(google_token_env, encoding="utf-8")

        google_creds_env = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
        if google_creds_env and not self.google_credentials_file.exists():
            self.google_credentials_file.parent.mkdir(parents=True, exist_ok=True)
            self.google_credentials_file.write_text(google_creds_env, encoding="utf-8")

        # Ensure local data directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.jobs_database_path.parent.mkdir(parents=True, exist_ok=True)

    def is_user_allowed(self, user_id: int) -> bool:
        """Check if a given Telegram user ID is authorized."""
        return user_id in self.allowed_user_ids


# Global singleton instance
settings = Settings()
