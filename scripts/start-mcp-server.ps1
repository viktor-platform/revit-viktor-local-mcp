[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$serverRoot = (Resolve-Path (Join-Path $PSScriptRoot "../revit-mcp-server")).Path
$output = Join-Path $serverRoot "publish/server"
$exe = Join-Path $output "RevitMcp.Server.exe"
$adapterSettings = Join-Path $env:LOCALAPPDATA "RevitMcp/adapter-settings.json"
if (Test-Path $adapterSettings) {
    $savedSettings = Get-Content -Raw -Path $adapterSettings | ConvertFrom-Json
    $adapterPort = [int]$savedSettings.Port
    if ($adapterPort -lt 1024 -or $adapterPort -gt 65535) {
        throw "Adapter settings contain an invalid port: $adapterPort"
    }
    $env:REVIT_MCP_BRIDGE_URL = "http://127.0.0.1:$adapterPort/"
    Write-Host "Using Revit adapter at $env:REVIT_MCP_BRIDGE_URL"
}
if (-not (Test-Path $exe)) {
    throw "MCP server is not published. Run .\scripts\setup-mcp-server.ps1 first."
}

function Test-Server {
    try {
        $response = Invoke-RestMethod "http://127.0.0.1:5099/" -TimeoutSec 2
        return $response.name -eq "Revit MCP server"
    }
    catch {
        return $false
    }
}

if (Test-Server) {
    Write-Host "Revit MCP server is already listening on port 5099." -ForegroundColor Green
    return
}
if (Get-Process -Name "RevitMcp.Server" -ErrorAction SilentlyContinue) {
    throw "RevitMcp.Server is running but its HTTP endpoint is unavailable. Inspect that process before starting another."
}

$process = Start-Process -FilePath $exe -WorkingDirectory $output -PassThru
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if (Test-Server) {
        Write-Host "Revit MCP server started on http://127.0.0.1:5099/mcp (PID $($process.Id))." -ForegroundColor Green
        return
    }
    if ($process.HasExited) {
        throw "Revit MCP server exited with code $($process.ExitCode)."
    }
    Start-Sleep -Milliseconds 500
}
throw "Revit MCP server did not become ready on port 5099. Check its console output."
