import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from viktor_mcp_worker.bridge import MCPBridge
from viktor_mcp_worker.settings import BridgeSettings


class MCPBridgeCLI:
    """Forward one VIKTOR worker request to the persistent bridge service."""

    def __init__(
        self,
        settings: BridgeSettings,
        *,
        workdir: Path | None = None,
    ) -> None:
        self.settings = settings
        self.workdir = workdir or Path.cwd()

    def run(self) -> int:
        result_path = self.workdir / "result.json"
        try:
            request_path = self.workdir / "request.json"
            if not request_path.exists():
                raise FileNotFoundError("Missing request.json")
            request = json.loads(request_path.read_text(encoding="utf-8"))
            if not isinstance(request, dict):
                raise ValueError("request.json must contain a JSON object")
            limits = request.get("limits", {})
            if limits is None:
                limits = {}
            if not isinstance(limits, dict):
                raise ValueError("'limits' must be a JSON object")
            timeout_seconds = int(limits.get("timeout_seconds", 300))
            if timeout_seconds <= 0:
                raise ValueError("'limits.timeout_seconds' must be positive")

            http_request = urllib.request.Request(
                self.settings.execute_url,
                data=json.dumps(request, ensure_ascii=False).encode(),
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(
                http_request, timeout=timeout_seconds + 10
            ) as response:
                result = json.loads(response.read().decode())
            if not isinstance(result, dict):
                raise RuntimeError("Bridge service returned a non-object JSON response")
        except urllib.error.HTTPError as exc:
            try:
                error_result = json.loads(exc.read().decode())
                result = (
                    error_result
                    if isinstance(error_result, dict)
                    else self._error_payload(type(exc).__name__, str(exc))
                )
            except (UnicodeDecodeError, json.JSONDecodeError):
                result = self._error_payload(type(exc).__name__, str(exc))
        except urllib.error.URLError as exc:
            result = self._error_payload(
                "BridgeServiceUnavailable",
                f"Could not reach bridge service at {self.settings.execute_url}: {exc}",
            )
        except Exception as exc:
            result = self._error_payload(type(exc).__name__, str(exc))

        result_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return 0

    def _error_payload(self, error_type: str, message: str) -> dict[str, Any]:
        return {
            "schema_version": MCPBridge.schema_version,
            "status": "error",
            "error": {"type": error_type, "message": message},
        }


def main() -> int:
    return MCPBridgeCLI(BridgeSettings.from_environment()).run()


if __name__ == "__main__":
    raise SystemExit(main())
