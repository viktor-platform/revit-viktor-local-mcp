# Revit add-in and MCP server

The add-in reads the open Revit model and can color elements in the active view. A separate local MCP server exposes its tools to the VIKTOR worker bridge. Revit API calls run inside Revit through an `ExternalEvent`.

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
| `color_category_elements` | `categoryName`, `color` | `modelTitle`, `viewId`, `viewName`, `categoryName`, `coloredElementCount`, `color` |

The first two tools only read data. The color tool changes element overrides in one transaction. It sets projection and cut line colors and visible solid foreground fills. It keeps unrelated override settings, such as line weights and transparency.

### Color a category

In the VIKTOR chat, enter **Color all Walls red**. To call the MCP tool directly, use `color_category_elements` with:

~~~json
{
  "categoryName": "Doors",
  "color": "green"
}
~~~

Use the category name from `list_categories`, or its built-in name such as `OST_Walls`. Name matching ignores letter case. Built-in names also work when Revit uses another display language.

Color accepts common names such as `red`, `green`, `blue`, `orange` or `purple`, or a hex value such as `#008000`.

The scope is all existing element instances in that category in the open project. Their overrides apply only in the active view, including for instances that are currently hidden. Other views, materials and linked documents are unchanged. New elements do not inherit these per-element overrides. Revit Undo removes the change in one step.

Open a project and a view that supports graphics overrides, such as a plan, section or 3D view. An empty category returns `coloredElementCount: 0`.

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

   Keep `[Description]` text clear: it becomes the tool schema the LLM reads. The VIKTOR app exposes all server tools by default.

2. **Revit logic** a method on `ModelQueryService` (or a new service) in `RevitMcp.Core/Services/`, e.g. `int CountElements(Document doc, string categoryName)` using `FilteredElementCollector`.

3. **Handler** `RevitMcp.RevitAddin/Handlers/CountElementsHandler.cs`, modelled on `ListCategoriesHandler`. `Name` must be `"count_elements"`. Register it in `App.cs`, in the `CommandDispatcher` list.

4. **MCP tool** in `RevitMcp.Server/Tools/RevitTools.cs`:

   ~~~csharp
   [McpServerTool(Name = "count_elements", ReadOnly = true, Idempotent = true, Destructive = false, OpenWorld = false)]
   [Description("Count the elements of one category in the open model.")]
   public Task<object> CountElements(CountElementsRequest request, CancellationToken cancellationToken = default)
       => InvokeToolAsync("count_elements", request, cancellationToken);
   ~~~

5. Rebuild the add-in (Revit closed), republish and restart the server. The VIKTOR app lists the server's tools at run time, so it needs no change (see [viktor-app](../viktor-app/README.md#where-tools-come-from)).

JSON property names are camelCase on the wire (`CategoryName` → `categoryName`).

## Troubleshooting

- **Build cannot find Revit DLLs:** check the year and `-RevitInstallDir`.
- **DLL locked:** close Revit before rebuilding; stop the server before republishing.
- **Add-in missing in Revit:** confirm `RevitMcp.RevitAddin.addin` exists in `%APPDATA%\Autodesk\Revit\Addins\<year>`, then restart Revit.
- **"No active document":** open a model in Revit.
- **Connection refused:** make sure the adapter is running (ribbon button) and run `scripts\check-local-services.ps1`.
