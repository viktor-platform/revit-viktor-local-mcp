[CmdletBinding()]
param(
    [string]$TargetDir = "C:\VIKTOR\MCPWorker",
    [switch]$SkipCopy,
    [switch]$Dev
)

$ErrorActionPreference = "Stop"

function Assert-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

$sourceDir = (Resolve-Path (Join-Path $PSScriptRoot "../viktor-mcp-worker")).Path

Write-Host "Source: $sourceDir" -ForegroundColor Cyan
Write-Host "Target: $TargetDir" -ForegroundColor Cyan

# 1. Ensure uv is installed.
if (-not (Assert-Command -Name "uv")) {
    Write-Host "uv not found on PATH. Installing uv..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"

    # uv installs to %USERPROFILE%\.local\bin by default; make it visible to this session.
    $uvBin = Join-Path $env:USERPROFILE ".local\bin"
    if (Test-Path $uvBin) {
        $env:PATH = "$uvBin;$env:PATH"
    }

    if (-not (Assert-Command -Name "uv")) {
        throw "uv installation finished but 'uv' is still not on PATH. Open a new shell and re-run this script."
    }
}
Write-Host "uv version: $(uv --version)" -ForegroundColor Green

# 2. Copy the worker project onto the target machine/location, unless running in place.
if (-not $SkipCopy -and $sourceDir -ne $TargetDir) {
    Write-Host "Copying worker project to $TargetDir..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    robocopy $sourceDir $TargetDir /E /XD .venv .git __pycache__ .pytest_cache .ruff_cache /XF *.pyc /NFL /NDL /NJH /NJS
    # robocopy exit codes 0-7 are success; >=8 is an error.
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed while copying worker project (exit code $LASTEXITCODE)."
    }
}
elseif ($sourceDir -eq $TargetDir) {
    Write-Host "Source and target are the same directory; skipping copy." -ForegroundColor Yellow
}

# 3. Create the venv and install pinned dependencies via `uv sync`.
Push-Location $TargetDir
try {
    $syncArgs = @("sync")
    if (-not $Dev) {
        $syncArgs += "--no-dev"
    }

    Write-Host "Running: uv $($syncArgs -join ' ')" -ForegroundColor Cyan
    & uv @syncArgs
    if ($LASTEXITCODE -ne 0) {
        throw "uv sync failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

$serviceExe = Join-Path $TargetDir ".venv\Scripts\mcp-bridge-service.exe"
if (Test-Path $serviceExe) {
    Write-Host ""
    Write-Host "Worker environment ready." -ForegroundColor Green
    Write-Host "  Service executable: $serviceExe"
    Write-Host "  Start it with: $(Join-Path $PSScriptRoot 'start_mcp_bridge_service.bat')"
    Write-Host "  VIKTOR Desktop Generic YAML: $(Join-Path $PSScriptRoot 'viktor-desktop-generic.yaml')"
}
else {
    throw "uv sync completed but $serviceExe was not found. Check pyproject.toml [project.scripts]."
}
