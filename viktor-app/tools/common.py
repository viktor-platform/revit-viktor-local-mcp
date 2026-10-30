import json
from typing import Any

MAX_TOOL_OUTPUT_BYTES = 16 * 1024


def _serialize(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(text.encode("utf-8")) > MAX_TOOL_OUTPUT_BYTES:
        return json.dumps(
            {
                "status": "error",
                "errorType": "tool_output_too_large",
                "message": (
                    "The compact tool result exceeded 16 KiB. Narrow the request."
                ),
            },
            separators=(",", ":"),
        )
    return text


def tool_ok(message: str, data: Any = None) -> str:
    payload: dict[str, Any] = {"status": "ok", "message": message}
    if data is not None:
        payload["data"] = data
    return _serialize(payload)


def tool_error(error_type: str, message: str, retry_action: str | None = None) -> str:
    payload: dict[str, Any] = {
        "status": "error",
        "errorType": error_type,
        "message": message,
    }
    if retry_action:
        payload["retryAction"] = retry_action
    return _serialize(payload)
