[CmdletBinding()]
param(
    [string]$Url = "http://127.0.0.1:5099/mcp",
    [string]$Tool,
    [string]$Arguments = "{}"
)

$ErrorActionPreference = "Stop"

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH."
    }
}
$scriptPath = Join-Path $PSScriptRoot "test-mcp-server.py"

if (-not (Test-Path $scriptPath)) {
    throw "Python test script not found at $scriptPath"
}

Assert-Command -Name "python"

$argsList = @($scriptPath, "--url", $Url, "--arguments", $Arguments)

if ($Tool) {
    $argsList += @("--tool", $Tool)
}

& python @argsList
if ($LASTEXITCODE -ne 0) {
    throw "MCP server test failed with exit code $LASTEXITCODE"
}
