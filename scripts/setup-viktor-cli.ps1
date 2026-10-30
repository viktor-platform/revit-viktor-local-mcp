[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$downloadPage = "https://docs.viktor.ai/docs/create-apps/references/cli/"
if (-not (Get-Command "viktor-cli" -ErrorAction SilentlyContinue)) {
    Write-Warning "viktor-cli is not installed or is not on PATH."
    Write-Host "Opening the official CLI installer page. Install the Windows CLI, then run viktor-cli configure yourself." -ForegroundColor Yellow
    Start-Process $downloadPage
    throw "Run this script again after installing and configuring the VIKTOR CLI."
}

& viktor-cli check-system
if ($LASTEXITCODE -ne 0) {
    throw "VIKTOR CLI checks failed. Review the failing item above (PyPI/certificate access, Python, environment, or credentials) before retrying; reconfigure only if credentials failed."
}
Write-Host "VIKTOR CLI is installed and its environment checks passed." -ForegroundColor Green
Write-Host "Confirm the app appears in viktor-cli apps before installing the local VIKTOR app."
