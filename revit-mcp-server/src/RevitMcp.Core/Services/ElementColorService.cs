using Autodesk.Revit.DB;
using RevitMcp.Contracts;

namespace RevitMcp.Core.Services;

public sealed class ElementColorService
{
    // The handler owns the transaction. Only the active view's overrides change.
    public ColorCategoryElementsResult ColorCategoryElements(
        Document doc, ColorCategoryElementsRequest request)
    {
        request.Validate();
        var rgb = request.GetRgb();
        var view = doc.ActiveView;
        if (view is null || view.IsTemplate || !view.AreGraphicsOverridesAllowed())
        {
            throw new InvalidOperationException(
                "The active view does not support color overrides. Open a plan, section or 3D view.");
        }

        var category = FindCategory(doc, request.CategoryName.Trim());
        using var elements = new FilteredElementCollector(doc);
        var elementIds = elements.OfCategoryId(category.Id)
            .WhereElementIsNotElementType().ToElementIds();

        if (elementIds.Count > 0)
        {
            using var patterns = new FilteredElementCollector(doc);
            var solidFill = patterns.OfClass(typeof(FillPatternElement))
                .Cast<FillPatternElement>()
                .FirstOrDefault(pattern => pattern.GetFillPattern().IsSolidFill)
                ?? throw new InvalidOperationException("The model has no solid fill pattern.");
            var color = new Color(rgb.Red, rgb.Green, rgb.Blue);

            foreach (var elementId in elementIds)
            {
                // Keep existing line weights, transparency and other unrelated settings.
                using var settings = view.GetElementOverrides(elementId);
                settings.SetProjectionLineColor(color);
                settings.SetCutLineColor(color);
                settings.SetSurfaceForegroundPatternId(solidFill.Id);
                settings.SetSurfaceForegroundPatternColor(color);
                settings.SetSurfaceForegroundPatternVisible(true);
                settings.SetCutForegroundPatternId(solidFill.Id);
                settings.SetCutForegroundPatternColor(color);
                settings.SetCutForegroundPatternVisible(true);
                view.SetElementOverrides(elementId, settings);
            }
        }

        return new ColorCategoryElementsResult
        {
            ModelTitle = doc.Title,
            ViewId = view.Id.Value,
            ViewName = view.Name,
            CategoryName = category.Name,
            ColoredElementCount = elementIds.Count,
            Color = $"#{rgb.Red:X2}{rgb.Green:X2}{rgb.Blue:X2}"
        };
    }

    private static Category FindCategory(Document doc, string name)
    {
        foreach (Category category in doc.Settings.Categories)
        {
            if (string.Equals(category.Name, name, StringComparison.OrdinalIgnoreCase))
            {
                return category;
            }
        }

        if (Enum.TryParse<BuiltInCategory>(name, true, out var builtInCategory)
            && Enum.IsDefined(typeof(BuiltInCategory), builtInCategory)
            && string.Equals(builtInCategory.ToString(), name, StringComparison.OrdinalIgnoreCase))
        {
            var category = Category.GetCategory(doc, builtInCategory);
            if (category is not null)
            {
                return category;
            }
        }

        throw new ArgumentException(
            $"Category '{name}' was not found. Use list_categories to get a category name.");
    }
}
