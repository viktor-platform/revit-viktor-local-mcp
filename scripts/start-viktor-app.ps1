[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
if (-not (Get-Command "viktor-cli" -ErrorAction SilentlyContinue)) {
    throw "viktor-cli is missing. Run .\scripts\setup-viktor-cli.ps1 first."
}
$appRoot = (Resolve-Path (Join-Path $PSScriptRoot "../viktor-app")).Path
Push-Location $appRoot
try {
    Write-Host "Starting the VIKTOR Develop app. Keep this terminal open; press Ctrl+C to stop." -ForegroundColor Cyan
    & viktor-cli start
    if ($LASTEXITCODE -ne 0) {
        throw "VIKTOR app start failed. Check viktor-cli apps and the registered_name in viktor.config.toml."
    }
}
finally {
    Pop-Location
}
