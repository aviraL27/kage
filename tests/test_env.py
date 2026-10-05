"""Basic sanity tests for environment and configuration."""

import pytest
from kage.config import settings


def test_settings_defaults():
    """Verify default settings values."""
    assert settings.timezone_name == "Asia/Kolkata"
    assert settings.tz is not None
    assert settings.llm_provider in ["gemini", "groq", "ollama"]
    assert settings.database_path.name == "kage.sqlite"
    assert settings.jobs_database_path.name == "jobs.sqlite"


def test_allowlist_check():
    """Verify allowlist checking behavior."""
    # Without allowed IDs, everything is rejected
    assert not settings.is_user_allowed(99999999)
    # Temporary mock allowlist
    settings.allowed_user_ids.add(12345)
    assert settings.is_user_allowed(12345)
    assert not settings.is_user_allowed(54321)
    settings.allowed_user_ids.remove(12345)
