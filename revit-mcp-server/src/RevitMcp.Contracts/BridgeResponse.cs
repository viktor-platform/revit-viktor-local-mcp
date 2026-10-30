namespace RevitMcp.Contracts;

public sealed record BridgeResponse(bool Success, object? Result, string? Error);
