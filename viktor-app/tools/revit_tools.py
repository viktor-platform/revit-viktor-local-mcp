"""Agent tools. Each tool = one thin wrapper over a Revit MCP tool.

Pattern used by every data tool:
  1. call the Revit MCP tool through the VIKTOR Generic worker,
  2. save the FULL result as a table (shown in the "Revit results" TableView),
  3. return only a SHORT summary to the LLM (keeps the model's context small).

The logic lives in plain async ``run_*`` functions so it can be tested without the
Agents SDK; the ``@function_tool`` wrappers below only forward arguments.
"""

from typing import Any

from agent.context import AgentContext
from agents import RunContextWrapper, function_tool
from state.tables import save_table

from tools.common import tool_error, tool_ok
from tools.worker_client import RevitWorkerClient, RevitWorkerError

SUMMARY_CATEGORY_LIMIT = 15
REVIT_UNAVAILABLE_HINT = (
    "Check that Revit is open with a model loaded, the Revit adapter is running, "
    "and the MCP server, worker bridge and VIKTOR Desktop worker are running."
)


async def run_get_model_name(
    storage_prefix: str,
    *,
    client: RevitWorkerClient | None = None,
    storage: Any = None,
) -> str:
    client = client or RevitWorkerClient.from_env()
    try:
        result = await client.call_tool("get_model_name")
    except RevitWorkerError as exc:
        return tool_error("revit_unavailable", str(exc), REVIT_UNAVAILABLE_HINT)

    rows = [
        ["Title", result.get("title", "")],
        ["File path", result.get("filePath") or "(not saved yet)"],
        ["Workshared", "Yes" if result.get("isWorkshared") else "No"],
        ["Revit version", result.get("revitVersion", "")],
    ]
    save_table(
        storage_prefix,
        title="Model",
        columns=["Property", "Value"],
        rows=rows,
        storage=storage,
    )
    return tool_ok("Model name read. Full details are in the Revit results table.", result)


async def run_list_categories(
    storage_prefix: str,
    *,
    include_empty: bool = False,
    model_categories_only: bool = True,
    client: RevitWorkerClient | None = None,
    storage: Any = None,
) -> str:
    client = client or RevitWorkerClient.from_env()
    try:
        result = await client.call_tool(
            "list_categories",
            {
                "includeEmpty": include_empty,
                "modelCategoriesOnly": model_categories_only,
            },
        )
    except RevitWorkerError as exc:
        return tool_error("revit_unavailable", str(exc), REVIT_UNAVAILABLE_HINT)

    categories = result.get("categories") or []
    if not isinstance(categories, list):
        return tool_error("bad_result", "Revit returned an unexpected category list.")

    save_table(
        storage_prefix,
        title="Categories",
        columns=["Category", "Built-in category", "Type", "Elements"],
        rows=[
            [
                row.get("name", ""),
                row.get("builtInCategory", ""),
                row.get("categoryType", ""),
                row.get("elementCount", 0),
            ]
            for row in categories
        ],
        storage=storage,
    )
    return tool_ok(
        f"Listed {len(categories)} categories. The full list is in the Revit "
        "results table; only the largest are included here.",
        {
            "modelTitle": result.get("modelTitle"),
            "categoryCount": result.get("categoryCount", len(categories)),
            "totalElementCount": result.get("totalElementCount"),
            "largestCategories": [
                {"name": row.get("name"), "elements": row.get("elementCount")}
                for row in categories[:SUMMARY_CATEGORY_LIMIT]
            ],
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
async def get_model_name(ctx: RunContextWrapper[AgentContext]) -> str:
    """Read the title, file path, workshared flag and Revit version of the open model.

    Also shows these properties in the Revit results table.
    """
    return await run_get_model_name(ctx.context.storage_prefix)


@function_tool
async def list_categories(
    ctx: RunContextWrapper[AgentContext],
    include_empty: bool = False,
    model_categories_only: bool = True,
) -> str:
    """List the element categories of the open model with element counts.

    Args:
        include_empty: Also list categories that have no elements in the model.
        model_categories_only: Only model categories (walls, pipes, ducts...). Set to
            false to include annotation categories such as tags and dimensions.

    Shows the full list in the Revit results table and returns the largest categories.
    """
    return await run_list_categories(
        ctx.context.storage_prefix,
        include_empty=include_empty,
        model_categories_only=model_categories_only,
    )


def build_agent_tools() -> list:
    """Every tool the agent may use. Add new @function_tool functions here."""
    return [report_progress, get_model_name, list_categories]
