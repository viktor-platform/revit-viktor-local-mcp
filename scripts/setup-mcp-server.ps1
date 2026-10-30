[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Debug"
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command "dotnet" -ErrorAction SilentlyContinue)) {
    throw "dotnet is not on PATH. Install the .NET 10 SDK, then retry."
}
if (Get-Process -Name "RevitMcp.Server" -ErrorAction SilentlyContinue) {
    throw "RevitMcp.Server is running. Stop it before publishing over its files, then retry."
}

$serverRoot = (Resolve-Path (Join-Path $PSScriptRoot "../revit-mcp-server")).Path
$project = Join-Path $serverRoot "src/RevitMcp.Server/RevitMcp.Server.csproj"
$output = Join-Path $serverRoot "publish/server"
if (-not (Test-Path $project)) {
    throw "MCP server project not found: $project"
}

& dotnet publish $project -c $Configuration -o $output --nologo
if ($LASTEXITCODE -ne 0) {
    throw "MCP server publish failed with exit code $LASTEXITCODE."
}
$exe = Join-Path $output "RevitMcp.Server.exe"
if (-not (Test-Path $exe)) {
    throw "Publish finished but the server executable is missing: $exe"
}
Write-Host "MCP server installed at $exe" -ForegroundColor Green
Write-Host "Start it with: .\scripts\start-mcp-server.ps1"
