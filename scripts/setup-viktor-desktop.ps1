[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$downloadPage = "https://docs.viktor.ai/docs/create-apps/software-integrations/viktor-desktop/"
$running = Get-Process -Name "VIKTOR-Desktop" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "VIKTOR Desktop is already running." -ForegroundColor Green
    return
}

$desktopExe = Join-Path $env:LOCALAPPDATA "Viktor\VIKTOR Desktop\VIKTOR-Desktop.exe"
if (Test-Path $desktopExe) {
    Start-Process -FilePath $desktopExe
    Write-Host "Started VIKTOR Desktop. Sign in to the correct VIKTOR environment in its window." -ForegroundColor Green
    return
}

Write-Warning "VIKTOR Desktop is not installed at the expected user location."
Write-Host "Opening the official installer page. Accept its terms, download the signed MSI, and complete the wizard." -ForegroundColor Yellow
Start-Process $downloadPage
throw "After installing VIKTOR Desktop, run this script again and sign in interactively."
