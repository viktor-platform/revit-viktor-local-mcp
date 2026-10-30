using Autodesk.Revit.UI;
using RevitMcp.Contracts;
using RevitMcp.Core.Services;
using System.Text.Json;

namespace RevitMcp.RevitAddin.Handlers;

public sealed class ListCategoriesHandler : IRevitCommandHandler
{
    public string Name => "list_categories";

    public object Execute(UIApplication uiApp, JsonElement args)
    {
        var doc = uiApp.ActiveUIDocument?.Document
            ?? throw new InvalidOperationException("No active document. Open a Revit model first.");
        return new ModelQueryService().ListCategories(
            doc, HandlerArguments.Deserialize<ListCategoriesRequest>(args));
    }
}
