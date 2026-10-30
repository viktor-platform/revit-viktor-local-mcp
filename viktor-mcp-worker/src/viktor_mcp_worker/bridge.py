import asyncio
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


@dataclass(slots=True)
class BridgeCommand:
    request: dict[str, Any]
    result: asyncio.Future[dict[str, Any]]


class MCPBridge:
    """Own a persistent MCP session and execute worker operations."""

    schema_version = "viktor.mcp.worker.v1"
    bridge_version = "0.1.0"

    def __init__(self, *, mcp_url: str, tool_cache_ttl_seconds: int) -> None:
        self.mcp_url = mcp_url
        self.tool_cache_ttl_seconds = tool_cache_ttl_seconds
        self._lock = asyncio.Lock()
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._initialize_result: dict[str, Any] | None = None
        self._tools_cache: list[dict[str, Any]] | None = None
        self._tools_cache_until = 0.0
        self._commands: asyncio.Queue[BridgeCommand | None] | None = None
        self._ready = asyncio.Event()
        self._stopped = asyncio.Event()
        self._accepting_requests = False

    @property
    def session_initialized(self) -> bool:
        return self._session is not None

    @property
    def tools_cached(self) -> bool:
        return self._tools_cache is not None

    async def close(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
        self._exit_stack = None
        self._session = None
        self._initialize_result = None

    async def serve(self) -> None:
        """Execute every MCP operation on one session-owning task."""
        if self._commands is not None:
            raise RuntimeError("MCP bridge is already serving requests")
        self._commands = asyncio.Queue()
        self._accepting_requests = True
        self._ready.set()
        try:
            while (command := await self._commands.get()) is not None:
                try:
                    response = await self.execute(command.request)
                except BaseException as exc:
                    if not command.result.done():
                        command.result.set_exception(exc)
                else:
                    if not command.result.done():
                        command.result.set_result(response)
        finally:
            await self.close()
            self._stopped.set()

    async def submit(self, request: dict[str, Any]) -> dict[str, Any]:
        """Queue a request for the persistent session-owning task."""
        await self._ready.wait()
        if self._commands is None or not self._accepting_requests:
            raise RuntimeError("MCP bridge is not running")
        result = asyncio.get_running_loop().create_future()
        await self._commands.put(BridgeCommand(request=request, result=result))
        return await result

    async def stop(self) -> None:
        """Stop accepting work and close the session on its owner task."""
        await self._ready.wait()
        if self._commands is not None and not self._stopped.is_set():
            self._accepting_requests = False
            await self._commands.put(None)
            await self._stopped.wait()

    def _to_jsonable(self, value: Any) -> Any:
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, dict):
            return {str(key): self._to_jsonable(item) for key, item in value.items()}
        if isinstance(value, list | tuple | set):
            return [self._to_jsonable(item) for item in value]
        if callable(model_dump := getattr(value, "model_dump", None)):
            try:
                return self._to_jsonable(
                    model_dump(mode="json", by_alias=True, exclude_none=True)
                )
            except TypeError:
                return self._to_jsonable(model_dump())
        if callable(dict_method := getattr(value, "dict", None)):
            return self._to_jsonable(dict_method())
        if hasattr(value, "__dict__"):
            return self._to_jsonable(vars(value))
        return str(value)

    async def _get_session(self) -> ClientSession:
        if self._session is not None:
            return self._session

        stack = AsyncExitStack()
        try:
            read_stream, write_stream, _ = await stack.enter_async_context(
                streamable_http_client(self.mcp_url)
            )
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            initialize_result = await session.initialize()
        except BaseException:
            await stack.aclose()
            raise

        self._exit_stack = stack
        self._session = session
        serialized = self._to_jsonable(initialize_result)
        self._initialize_result = (
            serialized if isinstance(serialized, dict) else {"value": serialized}
        )
        return session

    async def list_tools(self, *, force_refresh: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if (
            self._tools_cache is not None
            and not force_refresh
            and now < self._tools_cache_until
        ):
            return {
                "tools": self._tools_cache,
                "cached": True,
                "cache_expires_in_seconds": round(self._tools_cache_until - now),
            }

        async with self._lock:
            now = time.monotonic()
            if (
                self._tools_cache is not None
                and not force_refresh
                and now < self._tools_cache_until
            ):
                return {
                    "tools": self._tools_cache,
                    "cached": True,
                    "cache_expires_in_seconds": round(self._tools_cache_until - now),
                }

            try:
                result = await (await self._get_session()).list_tools()
                serialized = self._to_jsonable(result)
                if not isinstance(serialized, dict):
                    raise RuntimeError("MCP tools/list returned a non-object result")
                tools = serialized.get("tools")
                if not isinstance(tools, list) or not all(
                    isinstance(tool, dict) for tool in tools
                ):
                    raise RuntimeError("MCP tools/list returned an invalid tools value")
                self._tools_cache = tools
                self._tools_cache_until = time.monotonic() + self.tool_cache_ttl_seconds
                return {
                    "tools": tools,
                    "cached": False,
                    "cache_expires_in_seconds": self.tool_cache_ttl_seconds,
                }
            except BaseException:
                await self.close()
                raise

    async def call_tool(
        self, *, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        async with self._lock:
            try:
                result = await (await self._get_session()).call_tool(
                    name, arguments=arguments
                )
                serialized = self._to_jsonable(result)
                if not isinstance(serialized, dict):
                    return {"content": serialized}
                return serialized
            except BaseException:
                await self.close()
                raise

    async def call_tool_batch(
        self, *, tool_calls: list[dict[str, Any]]
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        async with self._lock:
            try:
                session = await self._get_session()
                for tool_call in tool_calls:
                    started_at = time.monotonic()
                    name = tool_call.get("name")
                    arguments = tool_call.get("arguments", {})

                    if not isinstance(name, str) or not name:
                        results.append(
                            {
                                "status": "error",
                                "error": {
                                    "type": "InvalidToolCall",
                                    "message": "Tool call requires a non-empty name.",
                                },
                            }
                        )
                        continue
                    if arguments is None:
                        arguments = {}
                    if not isinstance(arguments, dict):
                        results.append(
                            {
                                "name": name,
                                "status": "error",
                                "error": {
                                    "type": "InvalidArguments",
                                    "message": "Tool arguments must be a JSON object.",
                                },
                            }
                        )
                        continue

                    try:
                        result = await session.call_tool(name, arguments=arguments)
                        results.append(
                            {
                                "name": name,
                                "status": "success",
                                "result": self._to_jsonable(result),
                                "duration_ms": round(
                                    (time.monotonic() - started_at) * 1000
                                ),
                            }
                        )
                    except Exception as exc:
                        results.append(
                            {
                                "name": name,
                                "status": "error",
                                "error": {
                                    "type": type(exc).__name__,
                                    "message": str(exc),
                                },
                                "duration_ms": round(
                                    (time.monotonic() - started_at) * 1000
                                ),
                            }
                        )
                return {"results": results}
            except BaseException:
                await self.close()
                raise

    async def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        started_at = time.monotonic()
        operation = request.get("operation")

        if operation == "health.check":
            result: dict[str, Any] = {
                "bridge": "ok",
                "mcp_url": self.mcp_url,
                "session_initialized": self.session_initialized,
                "tools_cached": self.tools_cached,
            }
        elif operation == "tools.list":
            result = await self.list_tools(
                force_refresh=bool(request.get("force_refresh", False))
            )
        elif operation == "tools.call":
            tool = request.get("tool")
            if not isinstance(tool, dict):
                raise ValueError("'tool' must be a JSON object")
            name = tool.get("name")
            arguments = tool.get("arguments", {})
            if not isinstance(name, str) or not name:
                raise ValueError("'tool.name' is required")
            if arguments is None:
                arguments = {}
            if not isinstance(arguments, dict):
                raise ValueError("'tool.arguments' must be a JSON object")
            result = await self.call_tool(name=name, arguments=arguments)
        elif operation == "tools.call_batch":
            tool_calls = request.get("tool_calls", [])
            if not isinstance(tool_calls, list) or not all(
                isinstance(tool_call, dict) for tool_call in tool_calls
            ):
                raise ValueError("'tool_calls' must be a list of JSON objects")
            result = await self.call_tool_batch(tool_calls=tool_calls)
        else:
            raise ValueError(f"Unsupported operation: {operation}")

        return {
            "schema_version": self.schema_version,
            "status": "success",
            "operation": operation,
            "result": result,
            "diagnostics": {
                "bridge_version": self.bridge_version,
                "duration_ms": round((time.monotonic() - started_at) * 1000),
                "mcp_session_initialized": self.session_initialized,
            },
        }
