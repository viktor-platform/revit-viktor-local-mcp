[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$failed = $false
$adapterPort = 5057
$adapterSettings = Join-Path $env:LOCALAPPDATA "RevitMcp/adapter-settings.json"
if (Test-Path $adapterSettings) {
    $savedSettings = Get-Content -Raw -Path $adapterSettings | ConvertFrom-Json
    $adapterPort = [int]$savedSettings.Port
    if ($adapterPort -lt 1024 -or $adapterPort -gt 65535) {
        throw "Adapter settings contain an invalid port: $adapterPort"
    }
    if (-not $savedSettings.Enabled) {
        Write-Warning "Revit adapter is intentionally deactivated in its saved settings."
    }
}

function Test-LocalPort {
    param([int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $result = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $result.AsyncWaitHandle.WaitOne(2000)) {
            return $false
        }
        $client.EndConnect($result)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

foreach ($row in @(
    @{ Name = "Revit add-in bridge"; Port = $adapterPort },
    @{ Name = "Revit MCP server"; Port = 5099 },
    @{ Name = "Persistent worker bridge"; Port = 8765 }
)) {
    if (Test-LocalPort $row.Port) {
        Write-Host "$($row.Name): listening on $($row.Port)" -ForegroundColor Green
    }
    else {
        Write-Warning "$($row.Name): not listening on $($row.Port)"
        $failed = $true
    }
}

try {
    $health = Invoke-RestMethod "http://127.0.0.1:8765/health" -TimeoutSec 3
    Write-Host "Worker bridge health: $($health.status)" -ForegroundColor Green
}
catch {
    Write-Warning "Worker bridge health endpoint did not respond."
    $failed = $true
}

Write-Host "Confirm Generic is Running/Connected in VIKTOR Desktop and the VIKTOR Develop app is open."
if ($failed) {
    throw "One or more local services are unavailable. Follow the matching README section."
}
