[CmdletBinding()]
param(
    # Must match the -WorkerDir used with setup-all.ps1.
    [string]$WorkerDir = "C:\VIKTOR\MCPWorker",

    # Also start the VIKTOR app in its own window.
    [switch]$StartApp
)

# Starts the local services in order: MCP server (5099) -> worker bridge (8765) [-> app].
# Revit itself and the VIKTOR Desktop worker are started by you.
$ErrorActionPreference = "Stop"
$WorkerDir = [System.IO.Path]::GetFullPath($WorkerDir)

function Test-Health {
    try { return (Invoke-RestMethod "http://127.0.0.1:8765/health" -TimeoutSec 2).status -eq "success" }
    catch { return $false }
}

Write-Host "== MCP server" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "start-mcp-server.ps1")

Write-Host "`n== Worker bridge" -ForegroundColor Cyan
if (Test-Health) {
    Write-Host "Bridge is already running on port 8765." -ForegroundColor Green
}
else {
    $exe = Join-Path $WorkerDir ".venv\Scripts\mcp-bridge-service.exe"
    if (-not (Test-Path $exe)) { throw "Bridge not installed at $exe. Run .\scripts\setup-all.ps1 first." }
    $env:VIKTOR_MCP_SERVER_URL = "http://127.0.0.1:5099/mcp"
    $env:VIKTOR_MCP_BRIDGE_HOST = "127.0.0.1"
    $env:VIKTOR_MCP_BRIDGE_PORT = "8765"
    $env:VIKTOR_MCP_TOOL_CACHE_TTL_SECONDS = "300"
    Start-Process -FilePath $exe -WorkingDirectory $WorkerDir   # own window: close it to stop the bridge
    for ($i = 0; $i -lt 20 -and -not (Test-Health); $i++) { Start-Sleep -Milliseconds 500 }
    if (-not (Test-Health)) { throw "The bridge did not become healthy on http://127.0.0.1:8765/health." }
    Write-Host "Bridge started on http://127.0.0.1:8765" -ForegroundColor Green
}

if ($StartApp) {
    Write-Host "`n== VIKTOR app" -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "start-viktor-app.ps1")
    Write-Host "App starting in a new window; its Develop URL is printed there."
}

Write-Host "`n== Checking the chain" -ForegroundColor Cyan
try { & (Join-Path $PSScriptRoot "check-local-services.ps1") }
catch { Write-Warning "$($_.Exception.Message) If only the Revit adapter (5057) is missing, open Revit with a model." }
Write-Host "Also confirm the Generic worker shows Running/Connected in VIKTOR Desktop."
