"""Call Revit MCP tools through a VIKTOR Generic worker.

Chain: this app -> GenericAnalysis job -> VIKTOR Desktop Generic worker -> per-job CLI
-> persistent bridge (8765) -> Revit MCP server (5099) -> Revit add-in (5057).
"""

import json
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from viktor.external.generic import GenericAnalysis

WORKER_SCHEMA_VERSION = "viktor.mcp.worker.v1"
DEFAULT_EXECUTABLE_KEY = "mcp_bridge"
REQUEST_FILE = "request.json"
RESULT_FILE = "result.json"

# Allow-list of MCP tools this app may call. Add a name here when you add a tool.
ALLOWED_TOOLS = frozenset({"get_model_name", "list_categories"})
# MCP tools whose C# method takes a `request` object (see RevitTools.cs). Their
# arguments must be wrapped as {"request": {...}}; tools without it take no arguments.
TOOLS_WITH_REQUEST = frozenset({"list_categories"})


class RevitWorkerError(RuntimeError):
    """Recoverable VIKTOR worker, bridge, protocol, or Revit tool failure."""


def _result_field(result: Any, camel_name: str, snake_name: str) -> Any:
    if isinstance(result, dict):
        return result.get(camel_name, result.get(snake_name))
    return getattr(result, camel_name, getattr(result, snake_name, None))


def parse_tool_result(result: Any) -> dict[str, Any]:
    if bool(_result_field(result, "isError", "is_error")):
        raise RevitWorkerError("The Revit tool reported an error.")

    structured = _result_field(result, "structuredContent", "structured_content")
    if structured is not None:
        if not isinstance(structured, dict):
            raise RevitWorkerError("The Revit tool result was not a JSON object.")
        return structured

    content = _result_field(result, "content", "content") or []
    texts = []
    for item in content:
        text = (
            item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
        )
        if isinstance(text, str):
            texts.append(text)
    if len(texts) != 1:
        raise RevitWorkerError("The Revit tool did not return one JSON result.")
    try:
        payload = json.loads(texts[0])
    except json.JSONDecodeError as exc:
        raise RevitWorkerError("The Revit tool returned malformed JSON.") from exc
    if not isinstance(payload, dict):
        raise RevitWorkerError("The Revit tool result was not a JSON object.")
    return payload


def parse_worker_result(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RevitWorkerError("The VIKTOR worker returned an invalid result.")
    if payload.get("status") != "success":
        raise RevitWorkerError(
            "The VIKTOR worker could not reach the local Revit tool bridge."
        )
    if payload.get("operation") != "tools.call":
        raise RevitWorkerError("The VIKTOR worker returned an unexpected operation.")
    return parse_tool_result(payload.get("result"))


def _decode_output(output_file: Any) -> dict[str, Any]:
    if output_file is None:
        raise RevitWorkerError("The VIKTOR worker returned no result file.")
    getvalue = getattr(output_file, "getvalue", None)
    if not callable(getvalue):
        raise RevitWorkerError("The VIKTOR worker result file could not be read.")
    raw = getvalue()
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RevitWorkerError("The VIKTOR worker result was not UTF-8.") from exc
    if not isinstance(raw, str):
        raise RevitWorkerError("The VIKTOR worker result was not text.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RevitWorkerError("The VIKTOR worker returned malformed JSON.") from exc
    return parse_worker_result(payload)


def build_tool_arguments(name: str, request: dict[str, Any] | None) -> dict[str, Any]:
    """Shape MCP tool arguments the way the C# server expects them."""
    if name in TOOLS_WITH_REQUEST:
        return {"request": request or {}}
    if request:
        raise RevitWorkerError(f"Revit tool {name!r} does not take arguments.")
    return {}


@dataclass(frozen=True)
class RevitWorkerClient:
    executable_key: str = DEFAULT_EXECUTABLE_KEY
    timeout_seconds: int = 180

    @classmethod
    def from_env(cls) -> "RevitWorkerClient":
        executable_key = os.getenv(
            "VIKTOR_MCP_WORKER_EXECUTABLE_KEY", DEFAULT_EXECUTABLE_KEY
        ).strip()
        if not executable_key:
            raise RevitWorkerError(
                "VIKTOR_MCP_WORKER_EXECUTABLE_KEY must be non-empty."
            )
        return cls(executable_key=executable_key)

    async def call_tool(
        self, name: str, request: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if name not in ALLOWED_TOOLS:
            raise RevitWorkerError(f"Revit tool {name!r} is not allowed in this app.")

        worker_request = {
            "schema_version": WORKER_SCHEMA_VERSION,
            "operation": "tools.call",
            "tool": {
                "name": name,
                "arguments": build_tool_arguments(name, request),
            },
            "limits": {"timeout_seconds": self.timeout_seconds},
        }
        analysis = GenericAnalysis(
            files=[
                (
                    REQUEST_FILE,
                    BytesIO(json.dumps(worker_request).encode("utf-8")),
                )
            ],
            executable_key=self.executable_key,
            output_filenames=[RESULT_FILE],
        )
        try:
            analysis.execute(timeout=self.timeout_seconds + 30)
            return _decode_output(analysis.get_output_file(RESULT_FILE))
        except RevitWorkerError:
            raise
        except Exception as exc:
            raise RevitWorkerError(
                "Could not run the configured VIKTOR MCP worker. Keep the worker, "
                "local bridge, Revit, and the Revit MCP server running."
            ) from exc
