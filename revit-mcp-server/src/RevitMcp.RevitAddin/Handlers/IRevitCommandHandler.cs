using Autodesk.Revit.UI;
using System.Text.Json;

namespace RevitMcp.RevitAddin.Handlers;

public interface IRevitCommandHandler
{
    string Name { get; }

    object Execute(UIApplication uiApp, JsonElement args);
}
