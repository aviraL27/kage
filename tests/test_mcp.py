"""Comprehensive tests for FastMCP server and MCP client."""

from __future__ import annotations

import pytest
from kage.mcp.client import KageMCPClient, mcp_client
from kage.mcp.server import mcp_server


@pytest.mark.asyncio
async def test_mcp_server_registered_tools():
    """Verify that FastMCP server exposes all required command-center tools."""
    tools = await mcp_server.list_tools()
    tool_names = {t.name for t in tools}

    expected_tools = {
        "add_task",
        "list_tasks",
        "complete_task",
        "delete_task",
        "set_reminder",
        "remember_fact",
        "forget_fact",
        "list_memories",
        "list_calendar_events",
        "list_unread_emails",
        "list_github_notifications",
    }

    assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"
    assert len(tools) >= 11


@pytest.mark.asyncio
async def test_mcp_client_openai_tools_schema():
    """Verify MCP client translates tools into OpenAI function calling schema."""
    schemas = await mcp_client.get_openai_tools()
    assert len(schemas) >= 11

    # Check structure of each schema
    schema_map = {}
    for s in schemas:
        assert s.get("type") == "function"
        fn = s.get("function", {})
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert "properties" in fn["parameters"]
        schema_map[fn["name"]] = fn

    # Check specific tool parameter descriptions
    assert "add_task" in schema_map
    add_task_params = schema_map["add_task"]["parameters"]["properties"]
    assert "title" in add_task_params
    assert "Clear title" in add_task_params["title"].get("description", "")


@pytest.mark.asyncio
async def test_mcp_client_direct_tool_execution():
    """Verify direct MCP client execution of task management tools."""
    # 1. Add a task
    add_res = await mcp_client.call_tool("add_task", {"title": "Test MCP Tool Execution"})
    assert add_res["success"] is True
    assert "task" in add_res["result"]
    task_id = add_res["result"]["task"]["id"]

    # 2. List tasks
    list_res = await mcp_client.call_tool("list_tasks", {"status": "pending"})
    assert list_res["success"] is True
    tasks = list_res["result"]["tasks"]
    assert any(t["id"] == task_id for t in tasks)

    # 3. Complete task
    comp_res = await mcp_client.call_tool("complete_task", {"task_id": task_id})
    assert comp_res["success"] is True
    assert comp_res["result"]["task"]["status"] == "completed"


@pytest.mark.asyncio
async def test_mcp_client_confirmation_policy():
    """Verify that dangerous side effects enforce confirmation policy."""
    assert mcp_client.requires_confirmation("delete_task") is True
    assert mcp_client.requires_confirmation("add_task") is False
    assert mcp_client.requires_confirmation("list_tasks") is False

    # Create task to delete
    create_res = await mcp_client.call_tool("add_task", {"title": "Task to Delete"})
    task_id = create_res["result"]["task"]["id"]

    # Attempt delete without confirmation
    del_res = await mcp_client.call_tool("delete_task", {"task_id": task_id, "confirmed": False})
    assert del_res["success"] is True
    assert del_res["result"].get("confirmation_required") is True

    # Attempt delete with confirmation
    confirmed_res = await mcp_client.call_tool("delete_task", {"task_id": task_id, "confirmed": True})
    assert confirmed_res["success"] is True
    assert "successfully deleted" in confirmed_res["result"].get("message", "")


@pytest.mark.asyncio
async def test_mcp_client_memory_tools():
    """Verify persistent memory tools via MCP client."""
    # 1. Remember fact
    rem_res = await mcp_client.call_tool(
        "remember_fact",
        {"key": "test_mcp_drink", "value": "Matcha Latte", "category": "preference"},
    )
    assert rem_res["success"] is True
    assert rem_res["result"]["memory"]["value"] == "Matcha Latte"

    # 2. List memories
    list_res = await mcp_client.call_tool("list_memories", {"category": "preference"})
    assert list_res["success"] is True
    memories = list_res["result"]["memories"]
    assert any(m["key"] == "test_mcp_drink" for m in memories)

    # 3. Forget fact
    forget_res = await mcp_client.call_tool("forget_fact", {"key": "test_mcp_drink"})
    assert forget_res["success"] is True


@pytest.mark.asyncio
async def test_mcp_client_stdio_transport():
    """Verify true subprocess stdio MCP client-server communication over JSON-RPC."""
    client = KageMCPClient(mode="stdio")

    # Discover tools
    tools = await client.list_tools()
    tool_names = {t.name for t in tools}
    assert "add_task" in tool_names
    assert "list_tasks" in tool_names

    # Call tool over stdio
    res = await client.call_tool("list_tasks", {"status": "pending"})
    assert res["success"] is True
    assert "count" in res["result"]
    assert "tasks" in res["result"]
