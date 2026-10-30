using Autodesk.Revit.UI;

namespace RevitMcp.RevitAddin.Bridge;

internal sealed class BridgeExternalEventHandler : IExternalEventHandler
{
    private readonly Action<UIApplication> _execute;

    public BridgeExternalEventHandler(Action<UIApplication> execute)
    {
        _execute = execute;
    }

    public void Execute(UIApplication app)
    {
        _execute(app);
    }

    public string GetName()
    {
        return "Revit MCP bridge dispatcher";
    }
}
