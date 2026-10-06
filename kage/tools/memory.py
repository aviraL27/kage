"""Persistent memory tools for remembering facts and preferences in SQLite."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from kage.db import memory as db_memory
from kage.tools.registry import registry


# =====================================================================
# Argument Schemas
# =====================================================================

class RememberFactArgs(BaseModel):
    key: str = Field(
        ...,
        description="A short unique descriptor or topic for the memory (e.g. 'favorite_drink', 'working_hours', 'preferred_tone').",
    )
    value: str = Field(
        ...,
        description="The detailed fact, preference, or rule to remember.",
    )
    category: str = Field(
        "general",
        description="Category classification: 'preference', 'fact', 'routine', or 'general'.",
    )


class ForgetFactArgs(BaseModel):
    key: str = Field(
        ...,
        description="The unique key of the memory to remove.",
    )


class ListMemoriesArgs(BaseModel):
    category: Optional[str] = Field(
        None,
        description="Optional filter by category ('preference', 'fact', 'routine', 'general').",
    )


# =====================================================================
# Tool Implementations
# =====================================================================

@registry.register(
    name="remember_fact",
    description="Save or update a persistent user preference, fact, or instruction in SQLite that survives across sessions.",
    args_schema=RememberFactArgs,
)
def remember_fact(key: str, value: str, category: str = "general") -> Dict[str, Any]:
    saved = db_memory.set_memory(key=key, value=value, category=category)
    return {
        "message": f"Successfully remembered [{saved['category'].upper()}] '{saved['key']}': {saved['value']}",
        "memory": saved,
    }


@registry.register(
    name="forget_fact",
    description="Remove a previously stored fact or preference from persistent memory.",
    args_schema=ForgetFactArgs,
)
def forget_fact(key: str) -> Dict[str, Any]:
    deleted = db_memory.delete_memory(key=key)
    if deleted:
        return {"message": f"Successfully forgot memory '{key}'."}
    return {"error": f"Memory with key '{key}' was not found."}


@registry.register(
    name="list_memories",
    description="List all persistent memories, preferences, and facts stored across sessions.",
    args_schema=ListMemoriesArgs,
)
def list_memories(category: Optional[str] = None) -> Dict[str, Any]:
    memories = db_memory.list_memories(category=category)
    return {
        "count": len(memories),
        "memories": memories,
    }
