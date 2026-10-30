"""Agent tools built at run time from the MCP server's own tool list (``tools.list``).

The C# server is the single source of truth: name, description and input schema come
from it, so adding a tool in C# makes it available to the agent with no Python change.

Each MCP tool becomes one Agents SDK ``FunctionTool`` that:
  1. calls the tool through the VIKTOR Generic worker (``tools.call``),
  2. stores the FULL result in entity storage (``state.results``),
  3. returns the LLM a result small enough to read, plus a preview if it is large.
Presenting data (tables) is a separate concern: see ``tools/viktor_tools.py``.
"""

import json
import os
import time
from typing import Any

from agent.context import AgentContext
from agents import FunctionTool
from agents.tool_context import ToolContext
from state.results import save_result

from tools.common import tool_error, tool_ok
from tools.worker_client import RevitWorkerClient, RevitWorkerError

INLINE_LIMIT_BYTES = 6 * 1024  # results up to this size go to the LLM unchanged
PREVIEW_ITEMS = 5
TOOLS_CACHE_SECONDS = 300
ALLOW_WRITE_ENV = "VIKTOR_MCP_ALLOW_WRITE_TOOLS"
# Names implemented inside this app; an MCP tool with the same name is ignored.
RESERVED_NAMES = frozenset({"report_progress", "show_table"})
REVIT_UNAVAILABLE_HINT = (
    "Check that Revit is open with a model loaded, the Revit adapter is running, "
    "and the MCP server, worker bridge and VIKTOR Desktop worker are running."
)

_tools_cache: tuple[float, list[dict[str, Any]]] | None = None


def is_read_only(tool: dict[str, Any]) -> bool:
    """True when the server marks the tool read-only (``ReadOnly = true`` in C#)."""
    annotations = tool.get("annotations") or {}
    return annotations.get("readOnlyHint") is True


def allow_write_tools() -> bool:
    return os.getenv(ALLOW_WRITE_ENV, "").strip().lower() in {"1", "true", "yes"}


def summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return ``result`` unchanged when small, otherwise a preview with list counts."""
    text = json.dumps(result, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(text.encode("utf-8")) <= INLINE_LIMIT_BYTES:
        return result
    preview: dict[str, Any] = {}
    for key, value in result.items():
        if isinstance(value, list):
            preview[key] = {
                "count": len(value),
                "firstItems": value[:PREVIEW_ITEMS],
            }
        else:
            preview[key] = value
    return {"preview": preview, "truncated": True}


def make_mcp_tool(
    definition: dict[str, Any],
    *,
    client: RevitWorkerClient | None = None,
    storage: Any = None,
) -> FunctionTool:
    """Wrap one MCP tool definition (from ``tools.list``) as an agent tool."""
    name = str(definition["name"])
    schema = definition.get("inputSchema") or {}
    if schema.get("type") != "object":
        schema = {"type": "object", "properties": {}}

    async def invoke(ctx: ToolContext[AgentContext], args_json: str) -> str:
        try:
            arguments = json.loads(args_json) if args_json and args_json.strip() else {}
        except json.JSONDecodeError:
            return tool_error("validation_error", "Tool arguments were not valid JSON.")
        if not isinstance(arguments, dict):
            return tool_error("validation_error", "Tool arguments must be an object.")

        try:
            result = await (client or RevitWorkerClient.from_env()).call_tool(
                name, arguments
            )
        except RevitWorkerError as exc:
            return tool_error("revit_unavailable", str(exc), REVIT_UNAVAILABLE_HINT)

        save_result(ctx.context.storage_prefix, name, arguments, result, storage)
        return tool_ok(
            "Done. The full result is stored; call show_table to display it.",
            summarize_result(result),
        )

    description = (definition.get("description") or name).strip()
    return FunctionTool(
        name=name,
        description=description,
        params_json_schema=schema,
        on_invoke_tool=invoke,
        # MCP schemas are not "strict"-compatible (optional fields, nullable types).
        strict_json_schema=False,
    )


async def load_mcp_tools(
    client: RevitWorkerClient | None = None,
    *,
    storage: Any = None,
    use_cache: bool = True,
) -> tuple[list[FunctionTool], str | None]:
    """Build agent tools from ``tools.list``.

    Returns ``(tools, warning)``. ``warning`` explains why no tools were loaded (for
    example the worker or MCP server is down) so the agent can tell the user.
    """
    global _tools_cache
    now = time.monotonic()
    definitions: list[dict[str, Any]] | None = None
    if use_cache and _tools_cache and now - _tools_cache[0] < TOOLS_CACHE_SECONDS:
        definitions = _tools_cache[1]
    else:
        try:
            definitions = await (client or RevitWorkerClient.from_env()).list_tools()
        except RevitWorkerError as exc:
            return [], f"The Revit tools could not be loaded: {exc}"
        _tools_cache = (now, definitions)

    tools = [
        make_mcp_tool(definition, client=client, storage=storage)
        for definition in definitions
        if definition.get("name") not in RESERVED_NAMES
        and (is_read_only(definition) or allow_write_tools())
    ]
    if not tools:
        return [], (
            "The MCP server exposed no usable read-only tools. "
            f"Set {ALLOW_WRITE_ENV}=true to expose tools that can change Revit."
        )
    return tools, None


def clear_tools_cache() -> None:
    global _tools_cache
    _tools_cache = None
