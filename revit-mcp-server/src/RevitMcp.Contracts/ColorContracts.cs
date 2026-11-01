using System.ComponentModel;
using System.Globalization;

namespace RevitMcp.Contracts;

public sealed class ColorCategoryElementsRequest
{
    private static readonly Dictionary<string, int> NamedColors = new(StringComparer.OrdinalIgnoreCase)
    {
        ["black"] = 0x000000,
        ["white"] = 0xFFFFFF,
        ["red"] = 0xFF0000,
        ["green"] = 0x008000,
        ["blue"] = 0x0000FF,
        ["yellow"] = 0xFFFF00,
        ["orange"] = 0xFFA500,
        ["purple"] = 0x800080,
        ["pink"] = 0xFFC0CB,
        ["brown"] = 0xA52A2A,
        ["gray"] = 0x808080,
        ["grey"] = 0x808080,
        ["cyan"] = 0x00FFFF,
        ["aqua"] = 0x00FFFF,
        ["magenta"] = 0xFF00FF,
        ["fuchsia"] = 0xFF00FF,
        ["lime"] = 0x00FF00,
        ["navy"] = 0x000080,
        ["teal"] = 0x008080,
        ["olive"] = 0x808000,
        ["maroon"] = 0x800000,
        ["silver"] = 0xC0C0C0,
        ["gold"] = 0xFFD700,
        ["violet"] = 0xEE82EE,
        ["indigo"] = 0x4B0082
    };

    [Description("Category name from list_categories, such as Floors, Doors or Structural Columns, or its built-in name such as OST_Floors.")]
    public string CategoryName { get; init; } = string.Empty;

    [Description("Color name such as red, green or blue, or a hex color such as #008000.")]
    public string Color { get; init; } = string.Empty;

    public void Validate()
    {
        if (string.IsNullOrWhiteSpace(CategoryName))
        {
            throw new ArgumentException("Specify a category name, such as Walls or OST_Walls.");
        }

        GetRgb();
    }

    public (byte Red, byte Green, byte Blue) GetRgb()
    {
        var value = Color?.Trim() ?? string.Empty;
        if (!NamedColors.TryGetValue(value, out var rgb))
        {
            var hex = value.StartsWith("#", StringComparison.Ordinal) ? value.Substring(1) : value;
            if (hex.Length != 6 || !int.TryParse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out rgb))
            {
                throw new ArgumentException("Specify a common color name, such as green, or a hex color such as #008000.");
            }
        }

        return ((byte)(rgb >> 16), (byte)(rgb >> 8), (byte)rgb);
    }
}

public sealed class ColorCategoryElementsResult
{
    public string ModelTitle { get; init; } = string.Empty;

    public long ViewId { get; init; }

    public string ViewName { get; init; } = string.Empty;

    public string CategoryName { get; init; } = string.Empty;

    public int ColoredElementCount { get; init; }

    public string Color { get; init; } = string.Empty;
}
