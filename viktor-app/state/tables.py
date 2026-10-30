"""Tiny persistence layer between the agent tools and the table view.

Agent tools run inside the chat job; the TableView runs in a separate job. VIKTOR code
is stateless between jobs, so the tools save the latest table to entity storage and the
view reads it back.
"""

import json
from datetime import UTC, datetime
from typing import Any

import viktor as vkt

STORAGE_SCOPE = "entity"
TABLE_KEY_SUFFIX = "latest-table"


def storage_prefix(entity_id: int | None, workspace_id: int | None) -> str:
    """Key prefix that keeps every entity's data separate."""
    if entity_id is not None:
        owner = f"entity:{entity_id}"
    elif workspace_id is not None:
        owner = f"workspace:{workspace_id}"
    else:
        owner = "local"
    return f"revit-mcp-template:{owner}"


def _key(prefix: str) -> str:
    return f"{prefix}:{TABLE_KEY_SUFFIX}"


def _storage(storage: Any = None) -> Any:
    return storage or vkt.Storage()


def save_table(
    prefix: str,
    *,
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    storage: Any = None,
) -> None:
    """Store the table the TableView should show next."""
    if not columns:
        raise ValueError("A table needs at least one column.")
    for row in rows:
        if len(row) != len(columns):
            raise ValueError("Every row must have one value per column.")
    payload = {
        "title": title,
        "columns": columns,
        "rows": rows,
        "updatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _storage(storage).set(
        _key(prefix),
        data=vkt.File.from_data(json.dumps(payload, ensure_ascii=False, default=str)),
        scope=STORAGE_SCOPE,
    )


def read_table(prefix: str, storage: Any = None) -> dict[str, Any] | None:
    """Return the stored table, or None when nothing has been saved yet."""
    try:
        file = _storage(storage).get(_key(prefix), scope=STORAGE_SCOPE)
    except FileNotFoundError:
        return None
    value = file.getvalue_binary() if hasattr(file, "getvalue_binary") else file.getvalue()
    text = value.decode("utf-8") if isinstance(value, bytes) else str(value)
    payload = json.loads(text)
    return payload if isinstance(payload, dict) else None


def clear_table(prefix: str, storage: Any = None) -> None:
    try:
        _storage(storage).delete(_key(prefix), scope=STORAGE_SCOPE)
    except FileNotFoundError:
        pass
