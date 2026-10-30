[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
if (-not (Get-Command "viktor-cli" -ErrorAction SilentlyContinue)) {
    throw "viktor-cli is missing. Run .\scripts\setup-viktor-cli.ps1 first."
}
$appRoot = (Resolve-Path (Join-Path $PSScriptRoot "../viktor-app")).Path
foreach ($name in @("app.py", "requirements.txt", "viktor.config.toml")) {
    if (-not (Test-Path (Join-Path $appRoot $name))) {
        throw "VIKTOR app file is missing: $name"
    }
}

Push-Location $appRoot
try {
    & viktor-cli install
    if ($LASTEXITCODE -ne 0) {
        throw "VIKTOR app install failed. Check viktor-cli apps and use the account that maintains the registered_name in viktor.config.toml."
    }
}
finally {
    Pop-Location
}
Write-Host "VIKTOR app dependencies installed. Start with .\scripts\start-viktor-app.ps1." -ForegroundColor Green
