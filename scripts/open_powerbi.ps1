param([ValidateSet('real','synthetic')][string]$Mode = 'real', [string]$DesktopPath)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$projectPath = & .venv\Scripts\python.exe scripts\prepare_report.py --mode $Mode
if ($LASTEXITCODE -ne 0) { throw 'Preparing the local report failed' }
$candidates = @($DesktopPath, "$env:ProgramFiles\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
    "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\bin\PBIDesktop.exe")
$desktop = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $desktop) {
    $package = Get-AppxPackage -Name '*PowerBIDesktop*' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($package) { $desktop = Join-Path $package.InstallLocation 'bin\PBIDesktop.exe' }
}
if (-not $desktop -or -not (Test-Path -LiteralPath $desktop)) {
    throw "Power BI Desktop is unavailable. Install it, then rerun this script. Prepared project: $projectPath"
}
# This script is explicitly invoked to open an interactive report window.
Start-Process -FilePath $desktop -ArgumentList ('"{0}"' -f $projectPath) -WindowStyle Normal
