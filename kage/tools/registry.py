"""Strict Tool Registry with Pydantic validation, schema export, and audit logging."""

from __future__ import annotations

import inspect
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Type
from pydantic import BaseModel

from kage.db.audit import log_tool_execution

logger = logging.getLogger(__name__)


class ToolDefinition:
    """Represents a registered tool with schema and execution handler."""

    def __init__(
        self,
        name: str,
        description: str,
        args_schema: Type[BaseModel],
        handler: Callable[..., Any],
        requires_confirmation: bool = False,
    ) -> None:
        self.name = name
        self.description = description
        self.args_schema = args_schema
        self.handler = handler
        self.requires_confirmation = requires_confirmation

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert tool to OpenAI/Groq function calling schema."""
        schema = self.args_schema.model_json_schema()
        # Clean up unnecessary schema attributes for LLM compatibility
        schema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

    async def execute(self, raw_args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate arguments with Pydantic, execute handler, and audit log."""
        start_time = time.perf_counter()
        status = "success"
        result_summary = ""

        try:
            # 1. Validate arguments strictly against Pydantic schema
            validated_model = self.args_schema.model_validate(raw_args)
            validated_kwargs = validated_model.model_dump()

            # 2. Inject context if handler expects it
            sig = inspect.signature(self.handler)
            if "context" in sig.parameters:
                validated_kwargs["context"] = context or {}

            # 3. Execute handler (async or sync)
            if inspect.iscoroutinefunction(self.handler):
                result = await self.handler(**validated_kwargs)
            else:
                result = self.handler(**validated_kwargs)

            result_summary = str(result)[:300]
            return {"success": True, "result": result}

        except Exception as e:
            status = "error"
            result_summary = f"Error: {str(e)}"
            logger.error(f"Error executing tool '{self.name}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            log_tool_execution(
                tool_name=self.name,
                args=raw_args,
                result_summary=result_summary,
                latency_ms=latency_ms,
                status=status,
            )


class ToolRegistry:
    """Central registry holding all agent tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        args_schema: Type[BaseModel],
        requires_confirmation: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a tool function."""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            definition = ToolDefinition(
                name=name,
                description=description,
                args_schema=args_schema,
                handler=func,
                requires_confirmation=requires_confirmation,
            )
            self._tools[name] = definition
            return func

        return decorator

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Retrieve a tool definition by name."""
        return self._tools.get(name)

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Get all tool schemas in OpenAI function calling format."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    async def execute(
        self,
        name: str,
        raw_args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a tool by name with arguments and context."""
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' not found."}
        return await tool.execute(raw_args, context)


registry = ToolRegistry()
