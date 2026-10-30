using System.ComponentModel;

namespace RevitMcp.Contracts;

// Contracts are plain DTOs shared by the MCP server (which exposes them as the tool
// schema) and the Revit add-in (which fills them). Keep them free of Revit types.

public sealed class ModelNameResult
{
    public string Title { get; init; } = string.Empty;

    public string FilePath { get; init; } = string.Empty;

    public bool IsWorkshared { get; init; }

    public string RevitVersion { get; init; } = string.Empty;
}

public sealed class ListCategoriesRequest
{
    [Description("When true (default), only model categories are listed (walls, pipes, ducts...). Set to false to include annotation categories such as tags and dimensions.")]
    public bool ModelCategoriesOnly { get; init; } = true;

    [Description("When false (default), categories without any element instance in the model are omitted.")]
    public bool IncludeEmpty { get; init; }
}

public sealed class CategoryRow
{
    public string Name { get; init; } = string.Empty;

    public string BuiltInCategory { get; init; } = string.Empty;

    public string CategoryType { get; init; } = string.Empty;

    public int ElementCount { get; init; }
}

public sealed class ListCategoriesResult
{
    public string ModelTitle { get; init; } = string.Empty;

    public int CategoryCount { get; init; }

    public int TotalElementCount { get; init; }

    public IReadOnlyList<CategoryRow> Categories { get; init; } = Array.Empty<CategoryRow>();
}
