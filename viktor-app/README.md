# VIKTOR app: Revit agent

A `simple` VIKTOR app with:

- **`vkt.Chat`** field: an agent (OpenAI Agents SDK on VIKTOR's built-in LLM) that streams its answer and shows tool progress.
- **`vkt.TableView` "Revit results"**: shows the full result of the latest tool call.
- Two example tools that call Revit through the local MCP chain.

For the complete install order see the [root README](../README.md).

## Files

| File | Purpose |
| --- | --- |
| `app.py` | `Parametrization` (intro text + `vkt.Chat`) and `Controller` (`call_agent`, `results_table`) |
| `agent/runner.py` | Builds the agent, runs it, streams text and "Running/Done" tool rows into the chat |
| `agent/system_prompt.xml` | The agent's instructions: edit this to change behaviour |
| `tools/mcp_tools.py` | **Builds the agent's tools from the MCP server's `tools.list`**; each call stores its full result |
| `tools/viktor_tools.py` | Tools that live in the app: `show_table`, `report_progress` |
| `tools/worker_client.py` | `list_tools` / `call_tool` through a VIKTOR Generic worker (`GenericAnalysis`) |
| `state/results.py` | Stores raw MCP results in entity storage (`vkt.Storage`) |
| `state/table_builder.py` | Pure functions that turn a stored result into table columns and rows |
| `state/tables.py` | Stores the table the TableView shows |
| `viktor.config.toml` | App type, Python version, `registered_name` |

## Where tools come from

The C# MCP server is the **single source of truth**. At the start of each chat turn the app asks the worker for `tools.list` (cached for 5 minutes) and turns every tool into an agent tool using the server's name, description and input schema. Adding a tool in C# makes it available to the agent with no Python change.

Safety: only tools the server marks read-only (`ReadOnly = true` in C#, sent as `readOnlyHint`) are exposed. Set the environment variable `VIKTOR_MCP_ALLOW_WRITE_TOOLS=true` to expose the others.

If the worker or MCP server is down, the agent still starts, is told why no Revit tools are available, and tells the user.

## How the table view gets its data

Three separate steps, so MCP tools stay free of any VIKTOR presentation code:

1. **Run & store.** Every MCP tool call saves its **full** result to storage. The LLM receives the result, or a short preview with list counts when it is large (over 6 KB).
2. **Format.** The agent calls `show_table`, which reads the stored result (the data never passes through the LLM), picks the list, columns and sort order, and saves a table.
3. **Render.** `results_table` (the `TableView`) shows the saved table. Press **Refresh table** after the agent finishes.

`show_table` options: `source` (which tool's result, default the latest), `list_key`, `columns`, `sort_by`, `descending`, `title`, `limit`. Flat results are shown as Property / Value rows.

## Run the app

1. Set `registered_name` in `viktor.config.toml` to your own unique name and register it once:

   ~~~powershell
   viktor-cli create-app "My Revit Agent" --registered-name my-revit-agent
   ~~~

2. From the repository root: `scripts\setup-viktor-app.ps1`, then `scripts\start-viktor-app.ps1`.
3. Open the Develop URL, create an entity and chat.

The Revit tools only work when the full local chain is running. Without it, the agent answers that Revit is unavailable.

## Add a tool

Nothing to do here. Add the tool in C# ([steps](../revit-mcp-server/README.md#add-a-tool)), mark it `ReadOnly = true`, republish the MCP server and restart it; the app picks it up within 5 minutes (or on the next app restart).

Change only what the *agent* does with results by editing `agent/system_prompt.xml`, or add app-side behaviour (like `show_table`) in `tools/viktor_tools.py` and list it in `viktor_tools()`.

## Tests

~~~powershell
cd viktor-app
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt pytest pytest-asyncio
pytest
~~~

The tests use fakes for the worker, MCP tool list and storage, so they need neither Revit nor VIKTOR Desktop.

## Notes

- Tool results sent to the LLM are capped at 16 KiB (`tools/common.py`); large results are previewed and shown with `show_table`.
- The agent model is set by `MODEL_NAME` in `agent/runner.py`. Fair-usage errors (HTTP 429) are reported in the chat.
- The executable key defaults to `mcp_bridge`; override with the `VIKTOR_MCP_WORKER_EXECUTABLE_KEY` environment variable.
