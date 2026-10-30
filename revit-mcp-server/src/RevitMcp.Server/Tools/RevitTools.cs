using ModelContextProtocol;
using ModelContextProtocol.Server;
using RevitMcp.Contracts;
using System.ComponentModel;

namespace RevitMcp.Server.Tools;

/// <summary>
/// MCP tools exposed to clients. Each tool only forwards its request to the Revit add-in
/// through <see cref="BridgeClient"/>; the real work happens in a handler inside Revit.
/// Tool names here must match IRevitCommandHandler.Name in the add-in.
/// </summary>
[McpServerToolType]
public class RevitTools
{
    private readonly BridgeClient _bridge;

    public RevitTools(BridgeClient bridge)
    {
        _bridge = bridge;
    }

    [McpServerTool(Name = "get_model_name", ReadOnly = true, Idempotent = true, Destructive = false, OpenWorld = false)]
    [Description("Return the title, file path, workshared flag and Revit version of the model open in Revit.")]
    public Task<object> GetModelName(CancellationToken cancellationToken = default)
    {
        return InvokeToolAsync("get_model_name", new { }, cancellationToken);
    }

    [McpServerTool(Name = "list_categories", ReadOnly = true, Idempotent = true, Destructive = false, OpenWorld = false)]
    [Description("List the element categories of the open Revit model with their element counts, largest first.")]
    public Task<object> ListCategories(ListCategoriesRequest request, CancellationToken cancellationToken = default)
    {
        return InvokeToolAsync("list_categories", request, cancellationToken);
    }

    private async Task<object> InvokeToolAsync(string toolName, object request, CancellationToken cancellationToken)
    {
        var response = await _bridge.InvokeAsync(toolName, request, cancellationToken);
        if (!response.Success)
        {
            // McpException messages are returned to the client; other exceptions are hidden behind
            // a generic "An error occurred invoking ..." text.
            throw new McpException(response.Error ?? "The Revit add-in returned an unknown error.");
        }

        return response.Result!;
    }
}
