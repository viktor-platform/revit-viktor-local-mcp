"""Turn a stored MCP result (any JSON object) into table rows. Pure functions, no VIKTOR.

This is the "format" half of the table feature: ``show_table`` calls ``build_table``,
then ``state.tables.save_table`` stores the outcome and the TableView renders it.
"""

import json
import re
from typing import Any

DEFAULT_LIMIT = 1000
MAX_LIMIT = 5000


class TableBuildError(ValueError):
    """The stored result cannot be shown the way the caller asked."""


def _is_row_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(item, dict) for item in value)
    )


def _dig(result: Any, path: str) -> Any:
    """Follow a dotted path such as ``categories`` or ``data.items`` through dicts."""
    current = result
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise TableBuildError(f"No field {path!r} in the stored result.")
        current = current[part]
    return current


def find_rows(result: Any, list_key: str | None = None) -> tuple[str | None, list[dict]]:
    """Locate the list of row objects to tabulate.

    Returns ``(key_used, rows)``. ``rows`` is empty when the result has no list of
    objects; the caller then falls back to a Property/Value table.
    """
    if list_key:
        found = _dig(result, list_key)
        if not _is_row_list(found):
            raise TableBuildError(f"{list_key!r} is not a list of objects.")
        return list_key, found
    if _is_row_list(result):
        return None, result
    if isinstance(result, dict):
        candidates = [(k, v) for k, v in result.items() if _is_row_list(v)]
        if candidates:
            return max(candidates, key=lambda item: len(item[1]))
    return None, []


def humanize(key: str) -> str:
    """``elementCount`` -> ``Element count``."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", key).replace("_", " ").strip()
    return spaced[:1].upper() + spaced[1:].lower() if spaced else key


def cell(value: Any) -> Any:
    """Make any JSON value safe to show in one table cell."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def _sort_key(value: Any) -> tuple[int, Any]:
    """Order numbers, then text, then empty values; never compares mixed types."""
    if isinstance(value, bool | int | float):
        return (0, value)
    if value is None:
        return (2, "")
    return (1, str(value))


def _kind(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int | float):
        return "number"
    return "text"


def _as_text(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def normalize_columns(rows: list[list[Any]]) -> list[list[Any]]:
    """Make every column single-typed, which VIKTOR requires when sorting is enabled.

    ``None`` is allowed anywhere. A column holding more than one of text / number / bool
    is converted to text entirely (bools become Yes/No), so it still displays correctly.
    """
    if not rows:
        return rows
    mixed = [
        len({_kind(row[i]) for row in rows if row[i] is not None}) > 1
        for i in range(len(rows[0]))
    ]
    return [
        [_as_text(v) if mixed[i] and v is not None else v for i, v in enumerate(row)]
        for row in rows
    ]


def build_table(
    result: dict[str, Any],
    *,
    list_key: str | None = None,
    columns: list[str] | None = None,
    sort_by: str | None = None,
    descending: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return ``{"columns", "rows", "totalRows", "truncated"}``."""
    limit = max(1, min(int(limit), MAX_LIMIT))
    _, rows = find_rows(result, list_key)

    if not rows:
        # Flat result: show its fields as Property / Value rows.
        pairs = [[humanize(k), cell(v)] for k, v in result.items()]
        return {
            "columns": ["Property", "Value"],
            "rows": normalize_columns(pairs[:limit]),
            "totalRows": len(pairs),
            "truncated": len(pairs) > limit,
        }

    keys = list(columns) if columns else list(dict.fromkeys(k for r in rows for k in r))
    if columns:
        unknown = [k for k in keys if all(k not in r for r in rows)]
        if unknown:
            raise TableBuildError(f"Unknown column(s): {', '.join(unknown)}.")
    if sort_by:
        if all(sort_by not in r for r in rows):
            raise TableBuildError(f"Cannot sort by unknown column {sort_by!r}.")
        rows = sorted(rows, key=lambda r: _sort_key(r.get(sort_by)), reverse=descending)
    return {
        "columns": [humanize(k) for k in keys],
        "rows": normalize_columns([[cell(r.get(k)) for k in keys] for r in rows[:limit]]),
        "totalRows": len(rows),
        "truncated": len(rows) > limit,
    }
