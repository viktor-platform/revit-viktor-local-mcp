using System.Text.Json;

namespace RevitMcp.Contracts;

public sealed record BridgeRequest(string Tool, JsonElement Arguments);
