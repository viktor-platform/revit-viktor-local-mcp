[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Debug",

    [ValidateSet("2024", "2025", "2026", "2027")]
    [string]$RevitVersion = "2026",

    [string]$RevitInstallDir,

    [switch]$RegisterAddin,

    [ValidateSet("CurrentUser", "AllUsers")]
    [string]$AddinScope = "CurrentUser"
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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../revit-mcp-server")).Path
$solutionPath = Join-Path $repoRoot "RevitMcp.sln"
$serverProjectPath = Join-Path $repoRoot "src/RevitMcp.Server/RevitMcp.Server.csproj"

if (-not (Test-Path $solutionPath)) {
    throw "Solution file not found at $solutionPath"
}

if (-not (Test-Path $serverProjectPath)) {
    throw "Server project file not found at $serverProjectPath"
}

Assert-Command -Name "dotnet"

$buildArgs = @(
    "build"
    $solutionPath
    "-c"
    $Configuration
    "/p:RevitVersion=$RevitVersion"
)

if ($RevitInstallDir) {
    if (-not (Test-Path $RevitInstallDir)) {
        throw "RevitInstallDir does not exist: $RevitInstallDir"
    }

    $resolvedRevitInstallDir = (Resolve-Path $RevitInstallDir).Path
    $buildArgs += "/p:RevitInstallDir=$resolvedRevitInstallDir"
}

Write-Host "Building solution..." -ForegroundColor Cyan
Write-Host "  Solution: $solutionPath"
Write-Host "  Configuration: $Configuration"
Write-Host "  RevitVersion: $RevitVersion"
if ($RevitInstallDir) {
    Write-Host "  RevitInstallDir: $resolvedRevitInstallDir"
}

& dotnet @buildArgs
if ($LASTEXITCODE -ne 0) {
    throw "dotnet build failed with exit code $LASTEXITCODE"
}

if ($RegisterAddin) {
    $registerScript = Join-Path $PSScriptRoot "register-addin.ps1"
    $registerArgs = @{
        Configuration = $Configuration
        RevitVersion = $RevitVersion
        Scope = $AddinScope
    }

    if ($RevitInstallDir) {
        $tfm = switch ($RevitVersion) {
            "2024" { "net48" }
            "2027" { "net10.0-windows" }
            default { "net8.0-windows" }
        }
        $registerArgs["AssemblyPath"] = Join-Path $repoRoot "src/RevitMcp.RevitAddin/bin/$Configuration/$tfm/RevitMcp.RevitAddin.dll"
    }

    & $registerScript @registerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Add-in registration failed with exit code $LASTEXITCODE"
    }
}

$tfm = switch ($RevitVersion) {
    "2024" { "net48" }
    "2027" { "net10.0-windows" }
    default { "net8.0-windows" }
}
$serverProjectXml = [xml](Get-Content -Raw -Path $serverProjectPath)
$serverTargetFramework = $serverProjectXml.Project.PropertyGroup.TargetFramework | Select-Object -First 1

Write-Host ""
Write-Host "Build completed successfully." -ForegroundColor Green
Write-Host "Server DLL output: $(Join-Path $repoRoot "src/RevitMcp.Server/bin/$Configuration/$serverTargetFramework")"
Write-Host "Add-in DLL output: $(Join-Path $repoRoot "src/RevitMcp.RevitAddin/bin/$Configuration/$tfm")"
