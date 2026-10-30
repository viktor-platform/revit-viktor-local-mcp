# VIKTOR MCP Worker

Connects VIKTOR Desktop's Generic worker to a local MCP server (here: the Revit MCP server). It knows nothing about Revit, so it can front any MCP server. A persistent bridge keeps the MCP session open; Desktop launches a small CLI for each job.

**You start the persistent bridge. You do not start the per-job CLI yourself.**

For the complete setup and screenshots, see the [installation guide](../README.md).

## Install and configure

Run from this **viktor-mcp-worker** folder on the Windows computer running Revit. Python 3.12 is required.

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ..\scripts\setup-worker-env.ps1
~~~

The script installs uv if needed, copies this worker to **C:\VIKTOR\MCPWorker**, and installs its dependencies. Use `-TargetDir` only if you also update the Desktop configuration.

In VIKTOR Desktop:

1. Sign in to the environment containing the app.
2. Choose **Add → Generic**.
3. Paste [viktor-desktop-generic.yaml](../scripts/viktor-desktop-generic.yaml) into its configuration.
4. Save and start the worker. Confirm **Running/Connected**.

Restart the worker after changing its configuration.

## Start the bridge

Start the Revit MCP server first, then run:

~~~powershell
..\scripts\start_mcp_bridge_service.bat
~~~

Leave the terminal open. This script uses **http://127.0.0.1:5099/mcp** and starts the bridge on **127.0.0.1:8765**. Check **http://127.0.0.1:8765/health**.

Manual alternative, after installing to the default folder:

~~~powershell
$env:VIKTOR_MCP_SERVER_URL = "http://127.0.0.1:5099/mcp"; & "C:\VIKTOR\MCPWorker\.venv\Scripts\mcp-bridge-service.exe"
~~~

## Settings

| Environment variable | Purpose / default |
| --- | --- |
| `VIKTOR_MCP_SERVER_URL` | The batch script sets `http://127.0.0.1:5099/mcp` (the Revit MCP server). The package fallback is port 8000. |
| `VIKTOR_MCP_BRIDGE_HOST` | Listen address: `127.0.0.1` |
| `VIKTOR_MCP_BRIDGE_PORT` | Bridge port: `8765` |
| `VIKTOR_MCP_TOOL_CACHE_TTL_SECONDS` | Tool-list cache duration: `300` seconds |

Keep the bridge on localhost; no public tunnel is needed.

## How jobs work

Desktop runs `python -m viktor_mcp_worker.cli`. It reads `request.json`, calls the bridge's `POST /execute`, and writes `result.json`.

Supported operations: `health.check`, `tools.list`, `tools.call`, and `tools.call_batch`. For example:

~~~json
{
  "schema_version": "viktor.mcp.worker.v1",
  "operation": "tools.list"
}
~~~

If jobs fail, check Desktop's worker status, bridge health, and the Revit MCP server—in that order. Avoid running a second personal worker that competes for the same jobs.

## Developer checks

Run from this folder:

~~~powershell
uv sync
uvx ruff format --check .
uvx ruff check .
uvx ty check
uv run pytest
~~~

Shared Ruff configuration lives in the repository root (`ruff.toml`).
