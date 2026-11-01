using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using RevitMcp.Contracts;
using RevitMcp.Core.Services;
using System.Text.Json;

namespace RevitMcp.RevitAddin.Handlers;

public sealed class ColorCategoryElementsHandler : IRevitCommandHandler
{
    public string Name => "color_category_elements";

    public object Execute(UIApplication uiApp, JsonElement args)
    {
        var doc = uiApp.ActiveUIDocument?.Document
            ?? throw new InvalidOperationException("No active document. Open a Revit model first.");
        if (doc.IsReadOnly || doc.IsFamilyDocument)
        {
            throw new InvalidOperationException("Open an editable Revit project to color elements.");
        }

        var request = HandlerArguments.Deserialize<ColorCategoryElementsRequest>(args);
        request.Validate();

        using var transaction = new Transaction(doc, "Color category elements");
        if (transaction.Start() != TransactionStatus.Started)
        {
            throw new InvalidOperationException("Revit could not start the color transaction.");
        }

        var result = new ElementColorService().ColorCategoryElements(doc, request);
        if (transaction.Commit() != TransactionStatus.Committed)
        {
            throw new InvalidOperationException("Revit did not commit the color changes.");
        }

        return result;
    }
}
