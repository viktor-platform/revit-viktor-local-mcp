using System.Text.Json;

namespace RevitMcp.RevitAddin.Handlers;

internal static class HandlerArguments
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public static T Deserialize<T>(JsonElement args)
        where T : new()
    {
        if (args.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined)
        {
            return new T();
        }

        return args.Deserialize<T>(JsonOptions) ?? new T();
    }
}
