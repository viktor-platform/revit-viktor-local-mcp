# Revit + VIKTOR MCP agent template

A minimal, working starting point for a **VIKTOR chat agent that talks to a live Revit model**. It ships with two read-only example tools and a table view, so you can see the whole chain working before adding your own tools.

| Example tool | What it does |
| --- | --- |
| `get_model_name` | Title, file path, workshared flag and Revit version of the open model |
| `list_categories` | Element categories of the model with element counts |

Ask the agent *"List the categories in the model"* and the full result appears in the **Revit results** table next to the chat.

## How it fits together

```text
VIKTOR app (Chat + TableView; tools built from tools.list)
   │  GenericAnalysis job
   ▼
VIKTOR Desktop "Generic" worker ── runs the per-job CLI (viktor-mcp-worker)
   │  HTTP  127.0.0.1:8765
   ▼
Persistent bridge (viktor-mcp-worker)  ── keeps one MCP session open
   │  MCP over HTTP  127.0.0.1:5099/mcp
   ▼
Revit MCP server (revit-mcp-server, .NET)  ── exposes the tools
   │  HTTP  127.0.0.1:5057
   ▼
Revit add-in (revit-mcp-server)  ── runs the Revit API inside Revit
```

Everything runs on **one Windows computer** that has Revit. All ports are localhost; no public tunnel is needed.

| Folder | Contents |
| --- | --- |
| [viktor-app/](viktor-app/README.md) | VIKTOR app: `vkt.Chat` agent, `TableView`, `show_table` tool |
| [viktor-mcp-worker/](viktor-mcp-worker/README.md) | Python bridge between VIKTOR Desktop and the MCP server |
| [revit-mcp-server/](revit-mcp-server/README.md) | C# Revit add-in and MCP server |
| [scripts/](scripts/) | PowerShell setup/start scripts used below |

## Requirements

- Windows 10/11 and an installed **Revit 2024, 2025, 2026 or 2027**.
- **.NET 10 SDK** (builds the MCP server). Revit 2024 builds also need the **.NET Framework 4.8 Developer Pack**.
- **Python 3.12** and [uv](https://docs.astral.sh/uv/getting-started/installation/) (the setup script installs uv if missing).
- A **VIKTOR account** with developer access, the **VIKTOR CLI** and **VIKTOR Desktop**.

Open PowerShell in the **repository root** (the folder with this README and `scripts/`). Each step is one command. Keep long-running services (steps 6, 7, 8) in their own terminals.

## Quick start (clone and install)

Close Revit, then run in PowerShell:

~~~powershell
git clone https://github.com/viktor-platform/revit-viktor-local-mcp.git
cd revit-viktor-local-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-all.ps1
~~~

Then finish the manual steps the script prints (VIKTOR Desktop worker, app registration, Revit) and start the services with `start-all.ps1`. Details below.

## Quick setup (scripted)

Two scripts do the automatable parts of steps 3-7 below. Run them from the repository root.

~~~powershell
# 1. Check prerequisites only (changes nothing)
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-all.ps1 -CheckOnly

# 2. Install: worker, Revit add-in (build + register), MCP server, Desktop config
#    (close Revit first; add -RevitVersion 2026 etc. to pick a version, -InstallApp for the app)
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-all.ps1

# 3. After the manual steps it prints, start the services (add -StartApp for the VIKTOR app)
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1 -StartApp
~~~

What stays manual, because it needs you: signing in to VIKTOR Desktop and adding the Generic worker (the script puts the exact config on your clipboard), allowing the add-in when Revit asks, opening a model, and registering your VIKTOR app name. Use `-WorkerDir` with both scripts if `C:\VIKTOR\MCPWorker` is already taken. The step-by-step guide below explains each part and is the fallback if a script fails.

## 1. Install and configure the VIKTOR CLI

Download the Windows CLI from your VIKTOR environment's developer settings (`https://<your-environment>.viktor.ai/workspaces/settings/developer`), follow the [CLI installation guide](https://docs.viktor.ai/docs/create-apps/references/cli/), then run `viktor-cli configure` with your environment, email and developer token. Choose **Python 3.12**.

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-viktor-cli.ps1
~~~

## 2. Install or open VIKTOR Desktop

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-viktor-desktop.ps1
~~~

If Desktop is missing the script opens the [download page](https://docs.viktor.ai/docs/create-apps/software-integrations/viktor-desktop/). Install it, rerun the script and **sign in to the same VIKTOR environment** that will own the app. Don't run another standalone worker next to Desktop; two workers compete for jobs.

## 3. Install the worker and configure the Generic worker

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-worker-env.ps1
~~~

This copies [viktor-mcp-worker/](viktor-mcp-worker/) to `C:\VIKTOR\MCPWorker` and runs `uv sync --no-dev` there.

In VIKTOR Desktop choose **Add → Generic**, open the worker's `config.yaml`, and paste [scripts/viktor-desktop-generic.yaml](scripts/viktor-desktop-generic.yaml) (copy it with `Get-Content -Raw .\scripts\viktor-desktop-generic.yaml | Set-Clipboard`):

~~~yaml
executables:
  mcp_bridge:
    path: 'C:\VIKTOR\MCPWorker\.venv\Scripts\python.exe'
    arguments:
      - '-m'
      - 'viktor_mcp_worker.cli'
maxParallelProcesses: 1
~~~

Save, start the worker and confirm **Running/Connected**. Restart it after any change to `config.yaml`. Desktop launches the per-job CLI itself; you never start it by hand. The executable key `mcp_bridge` must match the app's default (`VIKTOR_MCP_WORKER_EXECUTABLE_KEY`).

### Why a Generic worker?

VIKTOR's Python worker receives a **script from the cloud app and runs it on your computer**. The Generic worker only runs **executables you listed yourself** in its `config.yaml`, so the cloud app cannot make the machine run new code. Here the executable is a tiny fixed command (`viktor_mcp_worker.cli`) that forwards a request to the local bridge, so Generic is the safer and simpler fit. Use the Python worker when the script itself must come from the app, as in the STAAD.Pro and ETABS integrations.

## 4. Build and register the Revit add-in

Close Revit, then run the line for your version (change the year for 2025/2026):

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-all.ps1 -RevitVersion 2027 -Configuration Debug -RegisterAddin -AddinScope CurrentUser
~~~

The script builds against that version's installed `RevitAPI.dll` and registers a manifest under `%APPDATA%\Autodesk\Revit\Addins\<year>`. Use `-AddinScope AllUsers` from an administrator terminal for a machine-wide install, or `-RevitInstallDir "D:\Apps\Autodesk\Revit 2027"` for a non-standard Revit location. Build each installed version separately.

Start the matching Revit version, allow the add-in to load when prompted, and **open a model**. The add-in starts a local adapter on `127.0.0.1:5057`. The **Revit Adapter** ribbon panel can stop/start it and change its port (saved in `%LOCALAPPDATA%\RevitMcp\adapter-settings.json`).

## 5. Install the local MCP server

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-mcp-server.ps1
~~~

Publishes `RevitMcp.Server.exe` into `revit-mcp-server\publish\server`. Stop a running server before republishing.

## 6. Start the MCP server

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-mcp-server.ps1
~~~

Waits for `http://127.0.0.1:5099/`; the MCP endpoint is `http://127.0.0.1:5099/mcp`. It reads the saved adapter port automatically.

## 7. Start the persistent worker bridge

~~~powershell
.\scripts\start_mcp_bridge_service.bat
~~~

Keep this terminal open. Health check: `http://127.0.0.1:8765/health`.

## 8. Create, install and start the VIKTOR app

The app needs its own name on the VIKTOR platform.

1. Pick a unique name, e.g. `my-revit-agent`, and set it as `registered_name` in [viktor-app/viktor.config.toml](viktor-app/viktor.config.toml).
2. Register it once: `cd viktor-app` then `viktor-cli create-app "My Revit Agent" --registered-name my-revit-agent`.
3. Install and start:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-viktor-app.ps1
~~~

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-viktor-app.ps1
~~~

Open the Develop URL printed by the CLI, create an entity, and chat: *"What is the name of the open model?"*

## 9. Verify the chain

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-local-services.ps1
~~~

Checks ports 5057 (add-in), 5099 (MCP server) and 8765 (bridge). To list the MCP tools directly:

~~~powershell
& "C:\VIKTOR\MCPWorker\.venv\Scripts\python.exe" .\scripts\test-mcp-server.py
~~~

A complete chain is: **Revit with a model open → add-in → MCP server → bridge → Generic worker Running in Desktop → VIKTOR app running.** If something fails, restart at the first missing component, not everything.

## Adding your own tool

Add it in C# only; the VIKTOR app builds its agent tools from the server's tool list at run time ([details](viktor-app/README.md#where-tools-come-from)). A worked example is in [revit-mcp-server/README.md](revit-mcp-server/README.md#add-a-tool):

1. **Contract**: request/result classes in `revit-mcp-server/src/RevitMcp.Contracts/`.
2. **Revit logic**: a method in `RevitMcp.Core/Services/` that uses the Revit API.
3. **Handler**: an `IRevitCommandHandler` in `RevitMcp.RevitAddin/Handlers/`, registered in `App.cs`.
4. **MCP tool**: a method in `RevitMcp.Server/Tools/RevitTools.cs` with the same name and `ReadOnly = true`.

Rebuild the add-in (step 4, with Revit closed), republish the server (step 5) and restart the services. Results can be shown in the table with no extra code: the agent calls `show_table`.

## Limitations

- Template / starting point, not a hardened product. Keep every service on localhost.
- The example tools only read the model. If you add tools that change Revit, run them inside a transaction in the handler and ask for explicit user confirmation first.
- The agent uses VIKTOR's built-in LLM (`vkt.ViktorOpenAI`), which has fair-usage limits.
