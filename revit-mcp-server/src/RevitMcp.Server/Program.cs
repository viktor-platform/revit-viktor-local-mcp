using RevitMcp.Server;
using RevitMcp.Server.Tools;

var builder = WebApplication.CreateBuilder(args);
var bridgeUrl =
    builder.Configuration["REVIT_MCP_BRIDGE_URL"] ??
    builder.Configuration["RevitBridge:Url"] ??
    "http://127.0.0.1:5057/";

var serverUrl =
    builder.Configuration["REVIT_MCP_SERVER_URL"] ??
    builder.Configuration["Server:Url"] ??
    "http://127.0.0.1:5099";

builder.Services.AddHttpClient();
builder.Services.AddSingleton(sp =>
{
    var httpClientFactory = sp.GetRequiredService<IHttpClientFactory>();
    return new BridgeClient(httpClientFactory.CreateClient(), bridgeUrl);
});
builder.Services
    .AddMcpServer()
    .WithHttpTransport()
    .WithTools<RevitTools>();

var app = builder.Build();

app.MapGet("/", () => Results.Ok(new
{
    Name = "Revit MCP server",
    Bridge = bridgeUrl,
    McpEndpoint = "/mcp"
}));

app.MapMcp("/mcp");

app.Run(serverUrl);
