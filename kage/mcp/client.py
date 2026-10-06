"""MCP Client for Kage agent with tool discovery, schema translation, and audit logging."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from kage.config import settings
from kage.db.audit import log_tool_execution
from kage.mcp.server import mcp_server

logger = logging.getLogger(__name__)

# Tools that have permanent side effects requiring user confirmation
SIDE_EFFECT_TOOLS = {"delete_task"}


class KageMCPClient:
    """Client for Model Context Protocol (MCP) servers.

    Supports both 'direct' (in-process FastMCP server) and 'stdio' (subprocess
    JSON-RPC) execution modes. Discovers tools, converts them into OpenAI/Groq
    compatible schemas, and enforces dual audit logging.
    """

    def __init__(self, mode: str = "direct") -> None:
        """Initialize MCP client with 'direct' or 'stdio' transport mode."""
        self.mode = mode
        self.server = mcp_server

    def requires_confirmation(self, tool_name: str) -> bool:
        """Check whether a tool call requires explicit user confirmation."""
        return tool_name in SIDE_EFFECT_TOOLS

    async def list_tools(self) -> List[Any]:
        """Discover all tools exposed by the MCP server."""
        if self.mode == "stdio":
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "kage.mcp.server"],
                env=os.environ.copy(),
            )
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    response = await session.list_tools()
                    return response.tools
        else:
            return await self.server.list_tools()

    async def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Fetch MCP tools and convert to OpenAI/Groq function calling schema."""
        tools = await self.list_tools()
        openai_tools: List[Dict[str, Any]] = []

        for tool in tools:
            schema = dict(tool.inputSchema) if tool.inputSchema else {"type": "object", "properties": {}}
            # Clean unnecessary titles that can confuse LLMs
            schema.pop("title", None)

            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": schema,
                },
            })

        return openai_tools

    async def _execute_direct(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool directly via the in-process FastMCP server instance."""
        res = await self.server.call_tool(name, arguments)
        return self._extract_result(res)

    async def _execute_stdio(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool via subprocess stdio JSON-RPC transport."""
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "kage.mcp.server"],
            env=os.environ.copy(),
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                call_res = await session.call_tool(name, arguments)
                return self._extract_result(call_res)

    def _extract_result(self, raw_result: Any) -> Any:
        """Parse text/JSON content out of MCP tool execution results."""
        # FastMCP direct call returns tuple of ([TextContent], {'result': ...})
        if isinstance(raw_result, tuple) and len(raw_result) >= 2 and isinstance(raw_result[1], dict):
            if "result" in raw_result[1]:
                return raw_result[1]["result"]

        # Check for CallToolResult or FastMCP list of TextContent
        content_list = None
        if hasattr(raw_result, "content"):
            content_list = raw_result.content
        elif isinstance(raw_result, list):
            content_list = raw_result

        if content_list and len(content_list) > 0:
            first_item = content_list[0]
            text = getattr(first_item, "text", str(first_item))
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return text

        return raw_result

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Invoke a tool with arguments, measure latency, and record audit log."""
        start_time = time.perf_counter()
        status = "success"
        result_summary = ""

        try:
            if self.mode == "stdio":
                result = await self._execute_stdio(name, arguments)
            else:
                result = await self._execute_direct(name, arguments)

            result_summary = str(result)[:300]
            return {"success": True, "result": result}

        except Exception as e:
            status = "error"
            result_summary = f"Error: {str(e)}"
            logger.error(f"Error executing MCP tool '{name}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            log_tool_execution(
                tool_name=name,
                args=arguments,
                result_summary=result_summary,
                latency_ms=latency_ms,
                status=status,
            )


# Default global MCP client instance
mcp_client = KageMCPClient(mode="direct")
