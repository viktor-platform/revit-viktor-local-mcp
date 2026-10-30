using Autodesk.Revit.UI;
using RevitMcp.Core.Services;
using System.Text.Json;

namespace RevitMcp.RevitAddin.Handlers;

public sealed class GetModelNameHandler : IRevitCommandHandler
{
    public string Name => "get_model_name";

    public object Execute(UIApplication uiApp, JsonElement args)
    {
        var doc = uiApp.ActiveUIDocument?.Document
            ?? throw new InvalidOperationException("No active document. Open a Revit model first.");
        return new ModelQueryService().GetModelName(doc);
    }
}
