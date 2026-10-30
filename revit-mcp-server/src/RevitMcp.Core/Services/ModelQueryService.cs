using Autodesk.Revit.DB;
using RevitMcp.Contracts;

namespace RevitMcp.Core.Services;

/// <summary>
/// Read-only queries against the active Revit document. These run inside Revit on the
/// UI thread (the add-in schedules them through an ExternalEvent), so they may call the
/// Revit API directly. Nothing here opens a transaction.
/// </summary>
public sealed class ModelQueryService
{
    public ModelNameResult GetModelName(Document doc)
    {
        return new ModelNameResult
        {
            Title = doc.Title,
            FilePath = doc.PathName ?? string.Empty,
            IsWorkshared = doc.IsWorkshared,
            RevitVersion = doc.Application.VersionNumber
        };
    }

    public ListCategoriesResult ListCategories(Document doc, ListCategoriesRequest request)
    {
        // One pass over all element instances, grouped by category id.
        var counts = new Dictionary<long, int>();
        foreach (var element in new FilteredElementCollector(doc).WhereElementIsNotElementType())
        {
            var category = element.Category;
            if (category is null)
            {
                continue;
            }

            var key = category.Id.Value;
            counts[key] = counts.TryGetValue(key, out var current) ? current + 1 : 1;
        }

        var rows = new List<CategoryRow>();
        foreach (Category category in doc.Settings.Categories)
        {
            if (request.ModelCategoriesOnly && category.CategoryType != CategoryType.Model)
            {
                continue;
            }

            counts.TryGetValue(category.Id.Value, out var count);
            if (count == 0 && !request.IncludeEmpty)
            {
                continue;
            }

            rows.Add(new CategoryRow
            {
                Name = category.Name,
                BuiltInCategory = Enum.IsDefined(typeof(BuiltInCategory), (int)category.Id.Value)
                    ? ((BuiltInCategory)(int)category.Id.Value).ToString()
                    : string.Empty,
                CategoryType = category.CategoryType.ToString(),
                ElementCount = count
            });
        }

        rows.Sort((a, b) =>
        {
            var byCount = b.ElementCount.CompareTo(a.ElementCount);
            return byCount != 0 ? byCount : string.Compare(a.Name, b.Name, StringComparison.OrdinalIgnoreCase);
        });

        return new ListCategoriesResult
        {
            ModelTitle = doc.Title,
            CategoryCount = rows.Count,
            TotalElementCount = rows.Sum(row => row.ElementCount),
            Categories = rows
        };
    }
}
