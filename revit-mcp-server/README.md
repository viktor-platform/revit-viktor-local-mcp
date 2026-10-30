# Revit add-in and MCP server

The add-in reads the open Revit model. A separate local MCP server exposes its tools to the VIKTOR worker bridge. Revit API calls run inside Revit through an `ExternalEvent`.

For the full installation order see the [root README](../README.md).

## Projects

| Project | Role |
| --- | --- |
| `RevitMcp.Contracts` | Plain DTOs shared by the server and add-in (`netstandard2.0`, no Revit types) |
| `RevitMcp.Core` | Revit API logic (`Services/`), no UI or HTTP |
| `RevitMcp.RevitAddin` | Revit `IExternalApplication`: ribbon panel, local HTTP adapter (5057), command handlers |
| `RevitMcp.Server` | ASP.NET MCP server (5099) that forwards each tool call to the adapter |

The add-in targets .NET Framework 4.8 for Revit 2024, .NET 8 for 2025–2026 and .NET 10 for 2027. Builds use the matching installation's `RevitAPI.dll` / `RevitAPIUI.dll`.

## Tools

| Tool | Arguments | Result |
| --- | --- | --- |
| `get_model_name` | none | `title`, `filePath`, `isWorkshared`, `revitVersion` |
| `list_categories` | `modelCategoriesOnly` (default true), `includeEmpty` (default false) | `modelTitle`, `categoryCount`, `totalElementCount`, `categories[]` (`name`, `builtInCategory`, `categoryType`, `elementCount`) |

Both are read-only and open no transactions.

## Build and register

Close Revit. From the **repository root**:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-all.ps1 -RevitVersion 2027 -Configuration Debug -RegisterAddin -AddinScope CurrentUser
~~~

Change the year for 2024/2025/2026; build each installed version separately. If the build worked but registration failed:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\register-addin.ps1 -RevitVersion 2027 -Configuration Debug -Scope CurrentUser
~~~

Then publish and start the MCP server (`scripts\setup-mcp-server.ps1`, `scripts\start-mcp-server.ps1`). Its endpoint is `http://127.0.0.1:5099/mcp`.

Environment variables for the server: `REVIT_MCP_BRIDGE_URL` (default `http://127.0.0.1:5057/`) and `REVIT_MCP_SERVER_URL` (default `http://127.0.0.1:5099`).

## Add a tool

Example: a `count_elements` tool that counts the elements of one category.

1. **Contract** `RevitMcp.Contracts/CountContracts.cs`

   ~~~csharp
   using System.ComponentModel;
   namespace RevitMcp.Contracts;

   public sealed class CountElementsRequest
   {
       [Description("Exact category name, e.g. Walls.")]
       public string CategoryName { get; init; } = string.Empty;
   }
   ~~~

   Keep `[Description]` text clear: it becomes the tool schema the LLM reads.

2. **Revit logic** a method on `ModelQueryService` (or a new service) in `RevitMcp.Core/Services/`, e.g. `int CountElements(Document doc, string categoryName)` using `FilteredElementCollector`.

3. **Handler** `RevitMcp.RevitAddin/Handlers/CountElementsHandler.cs`, modelled on `ListCategoriesHandler`. `Name` must be `"count_elements"`. Register it in `App.cs`, in the `CommandDispatcher` list.

4. **MCP tool** in `RevitMcp.Server/Tools/RevitTools.cs`:

   ~~~csharp
   [McpServerTool(Name = "count_elements", ReadOnly = true, Idempotent = true, Destructive = false, OpenWorld = false)]
   [Description("Count the elements of one category in the open model.")]
   public Task<object> CountElements(CountElementsRequest request, CancellationToken cancellationToken = default)
       => InvokeToolAsync("count_elements", request, cancellationToken);
   ~~~

5. Rebuild the add-in (Revit closed), republish and restart the server, then add the tool on the VIKTOR side (see [viktor-app](../viktor-app/README.md#add-a-tool)).

JSON property names are camelCase on the wire (`CategoryName` → `categoryName`).

## Safety

The tools in this template are read-only. If you add tools that modify the model, wrap the change in a `Transaction` inside the handler, name it clearly, return what changed, and require explicit user confirmation in the agent prompt. Never expose arbitrary code execution to the agent.

The adapter and server are not authenticated: bind them to localhost only.

## Troubleshooting

- **Build cannot find Revit DLLs:** check the year and `-RevitInstallDir`.
- **DLL locked:** close Revit before rebuilding; stop the server before republishing.
- **Add-in missing in Revit:** confirm `RevitMcp.RevitAddin.addin` exists in `%APPDATA%\Autodesk\Revit\Addins\<year>`, then restart Revit.
- **"No active document":** open a model in Revit.
- **Connection refused:** make sure the adapter is running (ribbon button) and run `scripts\check-local-services.ps1`.
