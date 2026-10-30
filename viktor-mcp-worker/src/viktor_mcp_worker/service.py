import asyncio
import json
import sys
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast

from viktor_mcp_worker.bridge import MCPBridge
from viktor_mcp_worker.settings import BridgeSettings


class MCPBridgeHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying the bridge and its dedicated event loop."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        bridge: MCPBridge,
        event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.bridge = bridge
        self.event_loop = event_loop
        super().__init__(server_address, BridgeRequestHandler)


class BridgeRequestHandler(BaseHTTPRequestHandler):
    """Expose health and execution endpoints for the local worker CLI."""

    server_version = "VIKTORMCPBridge/0.1"

    @property
    def bridge_server(self) -> MCPBridgeHTTPServer:
        return cast(MCPBridgeHTTPServer, self.server)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stdout.write(f"{self.address_string()} - {format % args}\n")

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/health":
            self._send_json(404, {"status": "error", "message": "Not found"})
            return
        bridge = self.bridge_server.bridge
        self._send_json(
            200,
            {
                "status": "success",
                "bridge_version": bridge.bridge_version,
                "mcp_url": bridge.mcp_url,
                "session_initialized": bridge.session_initialized,
            },
        )

    def do_POST(self) -> None:
        if self.path != "/execute":
            self._send_json(404, {"status": "error", "message": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(content_length).decode())
            if not isinstance(request, dict):
                raise ValueError("Request body must be a JSON object")
            limits = request.get("limits", {})
            if limits is None:
                limits = {}
            if not isinstance(limits, dict):
                raise ValueError("'limits' must be a JSON object")
            timeout_seconds = int(limits.get("timeout_seconds", 300))
            if timeout_seconds <= 0:
                raise ValueError("'limits.timeout_seconds' must be positive")

            future = asyncio.run_coroutine_threadsafe(
                self.bridge_server.bridge.submit(request),
                self.bridge_server.event_loop,
            )
            self._send_json(200, future.result(timeout=timeout_seconds + 5))
        except FutureTimeoutError:
            future.cancel()
            self._send_json(
                504,
                {
                    "schema_version": MCPBridge.schema_version,
                    "status": "error",
                    "error": {
                        "type": "TimeoutError",
                        "message": "MCP bridge service timed out.",
                    },
                },
            )
        except Exception as exc:
            self._send_json(
                400 if isinstance(exc, ValueError | json.JSONDecodeError) else 500,
                {
                    "schema_version": MCPBridge.schema_version,
                    "status": "error",
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                },
            )


class MCPBridgeService:
    """Manage the MCP event loop and local HTTP server lifecycle."""

    def __init__(self, settings: BridgeSettings) -> None:
        self.settings = settings
        self.bridge = MCPBridge(
            mcp_url=settings.mcp_url,
            tool_cache_ttl_seconds=settings.tool_cache_ttl_seconds,
        )
        self.event_loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(
            target=self._run_event_loop,
            name="mcp-bridge-event-loop",
            daemon=True,
        )
        self.http_server = MCPBridgeHTTPServer(
            (settings.host, settings.port), self.bridge, self.event_loop
        )

    def _run_event_loop(self) -> None:
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_until_complete(self.bridge.serve())

    def run(self) -> None:
        self.loop_thread.start()
        print(
            f"MCP bridge service listening on "
            f"http://{self.settings.host}:{self.settings.port}"
        )
        print(f"Forwarding MCP calls to {self.settings.mcp_url}")
        try:
            self.http_server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def close(self) -> None:
        self.http_server.server_close()
        if self.loop_thread.is_alive():
            future = asyncio.run_coroutine_threadsafe(
                self.bridge.stop(), self.event_loop
            )
            try:
                future.result(timeout=5)
            except Exception:
                future.cancel()
            self.loop_thread.join(timeout=5)
        if not self.loop_thread.is_alive():
            self.event_loop.close()


def main() -> int:
    MCPBridgeService(BridgeSettings.from_environment()).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
