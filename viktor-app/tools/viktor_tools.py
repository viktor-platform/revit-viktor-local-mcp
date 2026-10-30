"""Tools implemented inside the VIKTOR app (not forwarded to Revit).

``show_table`` is the presentation half of the table feature. MCP tools only run and
store raw results; this tool reads a stored result, formats it, and saves it for the
"Revit results" TableView. The data never passes through the LLM.
"""

from typing import Any

from agent.context import AgentContext
from agents import RunContextWrapper, function_tool
from state.results import read_result, stored_tool_names
from state.table_builder import DEFAULT_LIMIT, TableBuildError, build_table
from state.tables import save_table

from tools.common import tool_error, tool_ok


def run_show_table(
    storage_prefix: str,
    *,
    source: str | None = None,
    list_key: str | None = None,
    columns: list[str] | None = None,
    sort_by: str | None = None,
    descending: bool = False,
    title: str | None = None,
    limit: int = DEFAULT_LIMIT,
    storage: Any = None,
) -> str:
    record = read_result(storage_prefix, source, storage=storage)
    if record is None:
        available = stored_tool_names(storage_prefix, storage=storage)
        return tool_error(
            "no_stored_result",
            f"No stored result for {source!r}." if source else "No stored result yet.",
            "Call a Revit data tool first"
            + (f" (stored: {', '.join(available)})." if available else "."),
        )
    try:
        table = build_table(
            record["result"],
            list_key=list_key,
            columns=columns,
            sort_by=sort_by,
            descending=descending,
            limit=limit,
        )
    except TableBuildError as exc:
        return tool_error(
            "table_error",
            str(exc),
            "Check the field names in the stored result and retry.",
        )

    save_table(
        storage_prefix,
        title=title or str(record["tool"]),
        columns=table["columns"],
        rows=table["rows"],
        storage=storage,
    )
    return tool_ok(
        f"Showing {len(table['rows'])} of {table['totalRows']} rows from "
        f"{record['tool']} in the Revit results table.",
        {
            "source": record["tool"],
            "columns": table["columns"],
            "totalRows": table["totalRows"],
            "truncated": table["truncated"],
        },
    )


@function_tool
def report_progress(message: str) -> str:
    """Send one short progress sentence to the user before a longer step."""
    message = " ".join(message.split()).strip()
    if not message:
        return tool_error("validation_error", "Provide a non-empty progress message.")
    if len(message) > 300:
        return tool_error(
            "validation_error", "Keep progress messages within 300 characters."
        )
    return tool_ok("Progress update delivered.")


@function_tool
def show_table(
    ctx: RunContextWrapper[AgentContext],
    source: str | None = None,
    list_key: str | None = None,
    columns: list[str] | None = None,
    sort_by: str | None = None,
    descending: bool = False,
    title: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> str:
    """Show a stored Revit tool result in the "Revit results" table next to the chat.

    The data is read from storage, so never repeat it here. Field names are the keys
    in the stored result (for example "name", "elementCount").

    Args:
        source: Name of the Revit tool whose stored result to show. Default: the most
            recently called tool.
        list_key: Which list in the result to tabulate. Default: the longest list of
            objects; flat results are shown as Property/Value rows.
        columns: Fields to include, in order. Default: all fields.
        sort_by: Field to sort rows by.
        descending: Sort from largest to smallest.
        title: Optional table title.
        limit: Maximum rows to show (default 1000, maximum 5000).
    """
    return run_show_table(
        ctx.context.storage_prefix,
        source=source,
        list_key=list_key,
        columns=columns,
        sort_by=sort_by,
        descending=descending,
        title=title,
        limit=limit,
    )


def viktor_tools() -> list:
    """Tools that live in this app. MCP tools are added at run time."""
    return [report_progress, show_table]
