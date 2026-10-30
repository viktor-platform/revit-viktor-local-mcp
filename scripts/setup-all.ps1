[CmdletBinding()]
param(
    # Revit year to build the add-in for. Default: the newest installed version.
    [ValidateSet("2024", "2025", "2026", "2027")]
    [string]$RevitVersion,

    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Debug",

    [ValidateSet("CurrentUser", "AllUsers")]
    [string]$AddinScope = "CurrentUser",

    # Where the MCP worker is installed. The generated VIKTOR Desktop config points here.
    [string]$WorkerDir = "C:\VIKTOR\MCPWorker",

    # Also run "viktor-cli install" for the app (the app must already be registered).
    [switch]$InstallApp,

    # Only check prerequisites; change nothing.
    [switch]$CheckOnly
)

# One-shot setup of everything that can be automated on this computer:
#   worker  ->  Revit add-in (build + register)  ->  MCP server (publish)  ->  Desktop config
# Manual steps that remain (printed at the end): VIKTOR Desktop sign-in + Generic worker,
# allowing the add-in in Revit, registering the VIKTOR app name.
$ErrorActionPreference = "Stop"
$WorkerDir = [System.IO.Path]::GetFullPath($WorkerDir)
$blockers = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Step([string]$Text) { Write-Host "`n== $Text" -ForegroundColor Cyan }
function Test-PortBusy([int]$Port) {
    [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------- prerequisites
Step "Checking prerequisites"

$installed = @("2027", "2026", "2025", "2024") | Where-Object {
    Test-Path (Join-Path $env:ProgramFiles "Autodesk\Revit $_\RevitAPI.dll")
}
if (-not $installed) {
    $blockers.Add("No Revit 2024-2027 found under '$env:ProgramFiles\Autodesk'. Install Revit, or build manually with -RevitInstallDir.")
}
elseif (-not $RevitVersion) {
    $RevitVersion = $installed[0]
    Write-Host "Revit versions found: $($installed -join ', '). Using $RevitVersion (override with -RevitVersion)."
}
elseif ($installed -notcontains $RevitVersion) {
    $blockers.Add("Revit $RevitVersion is not installed here (found: $($installed -join ', ')).")
}

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue) -or -not ((& dotnet --list-sdks) -match "^10\.")) {
    $blockers.Add(".NET 10 SDK not found. Install it from https://dotnet.microsoft.com/download")
}
if ($RevitVersion -eq "2024" -and -not (Test-Path "${env:ProgramFiles(x86)}\Reference Assemblies\Microsoft\Framework\.NETFramework\v4.8")) {
    $blockers.Add("Revit 2024 builds need the .NET Framework 4.8 Developer Pack.")
}
if (Get-Process -Name "Revit" -ErrorAction SilentlyContinue) {
    $msg = "Revit is running. Close it before building, or the add-in DLL is locked."
    if ($CheckOnly) { $warnings.Add($msg) } else { $blockers.Add($msg) }
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    $warnings.Add("uv is not installed; the worker step will install it.")
}
if (-not (Get-Command viktor-cli -ErrorAction SilentlyContinue)) {
    $warnings.Add("viktor-cli is not installed (needed for the app): run .\scripts\setup-viktor-cli.ps1")
}
if (-not (Test-Path (Join-Path $env:LOCALAPPDATA "Viktor\VIKTOR Desktop\VIKTOR-Desktop.exe"))) {
    $warnings.Add("VIKTOR Desktop not found: run .\scripts\setup-viktor-desktop.ps1")
}
foreach ($port in 5057, 5099, 8765) {
    if (Test-PortBusy $port) { $warnings.Add("Port $port is already in use (an earlier install may be running).") }
}
if ((Test-Path (Join-Path $WorkerDir "pyproject.toml")) -and -not (Test-Path (Join-Path $WorkerDir ".venv"))) {
    $warnings.Add("$WorkerDir exists but has no .venv; it will be overwritten with this repo's worker.")
}

foreach ($w in $warnings) { Write-Warning $w }
foreach ($b in $blockers) { Write-Host "BLOCKER: $b" -ForegroundColor Red }
if ($blockers.Count -gt 0) { throw "Fix the blockers above, then rerun." }
if ($CheckOnly) {
    Write-Host "`nPrerequisites OK (Revit $RevitVersion, worker dir $WorkerDir). Nothing was changed." -ForegroundColor Green
    return
}

# ---------------------------------------------------------------- installation
Step "1/4  MCP worker -> $WorkerDir"
& (Join-Path $PSScriptRoot "setup-worker-env.ps1") -TargetDir $WorkerDir

Step "2/4  Revit $RevitVersion add-in (build + register, $AddinScope)"
& (Join-Path $PSScriptRoot "build-all.ps1") -RevitVersion $RevitVersion -Configuration $Configuration -RegisterAddin -AddinScope $AddinScope

Step "3/4  MCP server (publish)"
if (Get-Process -Name "RevitMcp.Server" -ErrorAction SilentlyContinue) {
    Write-Host "Stopping the running MCP server so it can be republished."
    Stop-Process -Name "RevitMcp.Server" -Force
    Start-Sleep -Seconds 1
}
& (Join-Path $PSScriptRoot "setup-mcp-server.ps1") -Configuration $Configuration

Step "4/4  VIKTOR Desktop Generic worker config"
$python = Join-Path $WorkerDir ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Worker Python not found: $python" }
$quoted = $python.Replace("'", "''")
$multi = @"
executables:
  mcp_bridge:
    path: '$quoted'
    arguments:
      - '-m'
      - 'viktor_mcp_worker.cli'

maxParallelProcesses: 1
"@
# The Desktop editor auto-indents pasted multi-line text and breaks YAML, so paste this one-liner.
$one = "{executables: {mcp_bridge: {path: '$quoted', arguments: ['-m', 'viktor_mcp_worker.cli']}}, maxParallelProcesses: 1}"
Set-Content -Path (Join-Path $PSScriptRoot "viktor-desktop-generic.local.yaml") -Value $multi -Encoding utf8
Set-Content -Path (Join-Path $PSScriptRoot "viktor-desktop-generic.oneline.local.yaml") -Value $one -Encoding utf8 -NoNewline
Set-Clipboard -Value $one
Write-Host "Config written to scripts\viktor-desktop-generic.*.local.yaml and the one-line version is on your clipboard."

if ($InstallApp) {
    Step "App dependencies (viktor-cli install)"
    & (Join-Path $PSScriptRoot "setup-viktor-app.ps1")
}

# ---------------------------------------------------------------- what is left
Write-Host "`nAutomated setup finished." -ForegroundColor Green
Write-Host @"

Remaining manual steps:
  1. VIKTOR Desktop: sign in to your VIKTOR environment, Add -> Generic, click in the
     config editor, press Ctrl+A, Delete, Ctrl+V (the config is on your clipboard),
     save, start the worker and confirm Running/Connected.
  2. Register the VIKTOR app once (set registered_name in viktor-app\viktor.config.toml):
       cd viktor-app
       viktor-cli create-app "My Revit Agent" --registered-name <your-unique-name>
     then rerun this script with -InstallApp, or run .\scripts\setup-viktor-app.ps1.
  3. Start Revit $RevitVersion, allow the add-in when asked, and open a model.
  4. Start the services:  .\scripts\start-all.ps1 -WorkerDir "$WorkerDir" -StartApp
"@
