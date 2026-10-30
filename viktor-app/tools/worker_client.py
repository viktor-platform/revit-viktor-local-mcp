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


def parse_worker_result(payload: Any, operation: str) -> Any:
    """Check the bridge envelope and return its ``result`` field."""
    if not isinstance(payload, dict):
        raise RevitWorkerError("The VIKTOR worker returned an invalid result.")
    if payload.get("status") != "success":
        raise RevitWorkerError(
            "The VIKTOR worker could not reach the local Revit tool bridge."
        )
    if payload.get("operation") != operation:
        raise RevitWorkerError("The VIKTOR worker returned an unexpected operation.")
    return payload.get("result")


def _decode_output(output_file: Any) -> Any:
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
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RevitWorkerError("The VIKTOR worker returned malformed JSON.") from exc


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

    def _run(self, request: dict[str, Any]) -> Any:
        """Send one request file through the Generic worker and decode result.json."""
        analysis = GenericAnalysis(
            files=[(REQUEST_FILE, BytesIO(json.dumps(request).encode("utf-8")))],
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

    async def list_tools(self) -> list[dict[str, Any]]:
        """Tool definitions (name, description, inputSchema, annotations) from the server."""
        payload = self._run(
            {
                "schema_version": WORKER_SCHEMA_VERSION,
                "operation": "tools.list",
                "limits": {"timeout_seconds": self.timeout_seconds},
            }
        )
        result = parse_worker_result(payload, "tools.list")
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list) or not all(isinstance(t, dict) for t in tools):
            raise RevitWorkerError("The MCP server returned an invalid tool list.")
        return tools

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run one MCP tool. ``arguments`` are passed exactly as the tool schema defines."""
        payload = self._run(
            {
                "schema_version": WORKER_SCHEMA_VERSION,
                "operation": "tools.call",
                "tool": {"name": name, "arguments": arguments or {}},
                "limits": {"timeout_seconds": self.timeout_seconds},
            }
        )
        return parse_tool_result(parse_worker_result(payload, "tools.call"))
