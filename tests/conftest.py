"""Pytest configuration and global fixtures."""

import pytest
from kage.db.database import init_db


@pytest.fixture(autouse=True, scope="session")
def initialize_database():
    """Ensure database schema is up-to-date across all test modules."""
    init_db()
