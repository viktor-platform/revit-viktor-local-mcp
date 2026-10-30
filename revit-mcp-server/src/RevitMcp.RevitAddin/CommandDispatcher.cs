using Autodesk.Revit.UI;
using RevitMcp.RevitAddin.Handlers;
using System.Text.Json;

namespace RevitMcp.RevitAddin;

public sealed class CommandDispatcher
{
    private readonly Dictionary<string, IRevitCommandHandler> _handlers;

    public CommandDispatcher(IEnumerable<IRevitCommandHandler> handlers)
    {
        _handlers = handlers.ToDictionary(h => h.Name, StringComparer.OrdinalIgnoreCase);
    }

    public object Dispatch(UIApplication uiApp, string tool, JsonElement args)
    {
        if (!_handlers.TryGetValue(tool, out var handler))
        {
            throw new InvalidOperationException($"Unknown tool: {tool}");
        }

        return handler.Execute(uiApp, args);
    }
}
