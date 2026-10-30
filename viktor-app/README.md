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
| `agent/runner.py` | Runs the agent and streams text + "Running/Done" tool rows into the chat |
| `agent/system_prompt.xml` | The agent's instructions: edit this to change behaviour |
| `agent/context.py` | Values passed to every tool (the storage key prefix) |
| `tools/revit_tools.py` | The agent's tools |
| `tools/worker_client.py` | Calls MCP tools through a VIKTOR Generic worker (`GenericAnalysis`) |
| `state/tables.py` | Saves the latest table so the TableView can show it |
| `viktor.config.toml` | App type, Python version, `registered_name` |

## How the table view gets its data

VIKTOR jobs are stateless, so the chat job and the table job communicate through entity storage:

1. A tool calls Revit and saves the **full** result with `save_table(...)`.
2. The tool returns only a **short summary** to the LLM (small context, fewer mistakes).
3. `results_table` reads the stored table with `read_table(...)`. Press **Refresh table** after the agent finishes.

## Run the app

1. Set `registered_name` in `viktor.config.toml` to your own unique name and register it once:

   ~~~powershell
   viktor-cli create-app "My Revit Agent" --registered-name my-revit-agent
   ~~~

2. From the repository root: `scripts\setup-viktor-app.ps1`, then `scripts\start-viktor-app.ps1`.
3. Open the Develop URL, create an entity and chat.

The Revit tools only work when the full local chain is running. Without it, the agent answers that Revit is unavailable.

## Add a tool

1. In `tools/worker_client.py` add the MCP tool name to `ALLOWED_TOOLS`. If its C# method takes a `request` object, also add it to `TOOLS_WITH_REQUEST`.
2. In `tools/revit_tools.py` write a plain `run_<tool>(...)` function (call the worker, `save_table(...)`, return `tool_ok(...)`), a thin `@function_tool` wrapper, and add the wrapper to `build_agent_tools()`.
3. Optionally add a friendly name to `TOOL_DISPLAY_NAMES` in `agent/runner.py` and mention the tool in `agent/system_prompt.xml`.
4. Add a test next to `tests/test_tools.py` using `FakeClient` and `FakeStorage`.

## Tests

~~~powershell
cd viktor-app
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt pytest pytest-asyncio
pytest
~~~

The tests use fakes for the worker and storage, so they need neither Revit nor VIKTOR Desktop.

## Notes

- Tool results sent to the LLM are capped at 16 KiB (`tools/common.py`); put big data in the table instead.
- The agent model is set by `MODEL_NAME` in `agent/runner.py`. Fair-usage errors (HTTP 429) are reported in the chat.
- The executable key defaults to `mcp_bridge`; override with the `VIKTOR_MCP_WORKER_EXECUTABLE_KEY` environment variable.
