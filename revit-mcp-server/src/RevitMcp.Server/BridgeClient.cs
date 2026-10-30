using RevitMcp.Contracts;
using System.Text;
using System.Text.Json;

namespace RevitMcp.Server;

public sealed class BridgeClient
{
    private readonly HttpClient _httpClient;
    private readonly string _endpoint;
    private readonly JsonSerializerOptions _jsonOptions = new(JsonSerializerDefaults.Web);

    public BridgeClient(HttpClient httpClient, string endpoint)
    {
        _httpClient = httpClient;
        _endpoint = endpoint.TrimEnd('/');
    }

    public async Task<BridgeResponse> InvokeAsync(string tool, object args, CancellationToken cancellationToken = default)
    {
        var request = new BridgeRequest(tool, JsonSerializer.SerializeToElement(args, _jsonOptions));
        var json = JsonSerializer.Serialize(request, _jsonOptions);

        using var content = new StringContent(json, Encoding.UTF8, "application/json");
        using var response = await _httpClient.PostAsync(_endpoint, content, cancellationToken);
        var body = await response.Content.ReadAsStringAsync(cancellationToken);

        var result = JsonSerializer.Deserialize<BridgeResponse>(body, _jsonOptions);
        return result ?? new BridgeResponse(false, null, "Failed to parse bridge response.");
    }
}
