"""Raw MCP tool results, saved so other tools (for example ``show_table``) can use them.

Why store results instead of passing them through the LLM? Results can be large. The
agent only needs a short preview; the complete data stays in VIKTOR entity storage and
is referenced by tool name.

Storage facts (viktor SDK): keys are at most 256 characters, ``get``/``delete`` raise
``FileNotFoundError`` for a missing key, and ``list(prefix=...)`` lists keys by prefix.
"""

import json
from datetime import UTC, datetime
from typing import Any

import viktor as vkt

STORAGE_SCOPE = "entity"
LATEST = "_latest"


def _storage(storage: Any = None) -> Any:
    return storage or vkt.Storage()


def _key(prefix: str, name: str) -> str:
    return f"{prefix}:result:{name}"


def _put(key: str, payload: dict[str, Any], storage: Any) -> None:
    _storage(storage).set(
        key,
        data=vkt.File.from_data(json.dumps(payload, ensure_ascii=False, default=str)),
        scope=STORAGE_SCOPE,
    )


def _get(key: str, storage: Any) -> dict[str, Any] | None:
    try:
        file = _storage(storage).get(key, scope=STORAGE_SCOPE)
    except FileNotFoundError:
        return None
    value = file.getvalue_binary() if hasattr(file, "getvalue_binary") else file.getvalue()
    text = value.decode("utf-8") if isinstance(value, bytes) else str(value)
    payload = json.loads(text)
    return payload if isinstance(payload, dict) else None


def save_result(
    prefix: str,
    tool: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    storage: Any = None,
) -> None:
    """Store the latest result of ``tool`` and remember it as the latest overall."""
    _put(
        _key(prefix, tool),
        {
            "tool": tool,
            "arguments": arguments,
            "result": result,
            "savedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        storage,
    )
    _put(_key(prefix, LATEST), {"tool": tool}, storage)


def read_result(
    prefix: str, tool: str | None = None, storage: Any = None
) -> dict[str, Any] | None:
    """Return the stored record for ``tool`` (default: the most recent tool call)."""
    if tool is None:
        pointer = _get(_key(prefix, LATEST), storage)
        if pointer is None:
            return None
        tool = str(pointer.get("tool", ""))
    return _get(_key(prefix, tool), storage)


def stored_tool_names(prefix: str, storage: Any = None) -> list[str]:
    """Names of tools that have a stored result for this entity."""
    keys = _storage(storage).list(prefix=_key(prefix, ""), scope=STORAGE_SCOPE)
    start = len(_key(prefix, ""))
    return sorted(name for key in keys if (name := key[start:]) != LATEST)


def clear_results(prefix: str, storage: Any = None) -> None:
    store = _storage(storage)
    for key in list(store.list(prefix=_key(prefix, ""), scope=STORAGE_SCOPE)):
        try:
            store.delete(key, scope=STORAGE_SCOPE)
        except FileNotFoundError:
            pass
