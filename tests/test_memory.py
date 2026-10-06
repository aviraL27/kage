"""Unit and integration tests for Persistent Memory in SQLite and Prompt Injection."""

import pytest
from kage.db.database import init_db
from kage.db import memory as db_memory
from kage.llm.prompt import get_system_prompt
from kage.tools.registry import registry
import kage.tools  # Register all tools


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_db_memory_crud():
    """Verify SQLite CRUD operations for memory."""
    # Create
    mem = db_memory.set_memory("coffee", "Oat milk latte", category="preference")
    assert mem["key"] == "coffee"
    assert mem["value"] == "Oat milk latte"

    # Get
    fetched = db_memory.get_memory("coffee")
    assert fetched is not None
    assert fetched["value"] == "Oat milk latte"

    # Update on conflict
    updated = db_memory.set_memory("coffee", "Black coffee without sugar", category="preference")
    assert updated["value"] == "Black coffee without sugar"

    fetched2 = db_memory.get_memory("coffee")
    assert fetched2["value"] == "Black coffee without sugar"

    # List
    all_mems = db_memory.list_memories()
    assert any(m["key"] == "coffee" for m in all_mems)

    # Delete
    deleted = db_memory.delete_memory("coffee")
    assert deleted is True
    assert db_memory.get_memory("coffee") is None


@pytest.mark.asyncio
async def test_memory_tools_execution():
    """Verify remember_fact, list_memories, and forget_fact tools via registry."""
    # 1. remember_fact
    rem_res = await registry.execute(
        "remember_fact",
        {"key": "editor", "value": "VS Code with Vim keybindings", "category": "preference"},
    )
    assert rem_res["success"] is True
    assert "Successfully remembered" in rem_res["result"]["message"]

    # 2. list_memories
    list_res = await registry.execute("list_memories", {})
    assert list_res["success"] is True
    keys = [m["key"] for m in list_res["result"]["memories"]]
    assert "editor" in keys

    # 3. forget_fact
    forget_res = await registry.execute("forget_fact", {"key": "editor"})
    assert forget_res["success"] is True
    assert "Successfully forgot" in forget_res["result"]["message"]


def test_system_prompt_injects_memories():
    """Verify prompt generator injects persistent memories into system prompt."""
    db_memory.set_memory("focus_time", "No meetings before 11 AM", category="routine")

    prompt = get_system_prompt()
    assert "USER PREFERENCES & PERSISTENT KNOWLEDGE:" in prompt
    assert "focus_time: No meetings before 11 AM" in prompt

    # Clean up
    db_memory.delete_memory("focus_time")
