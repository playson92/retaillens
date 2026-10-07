param([ValidateSet('synthetic','real')][string]$Mode = 'synthetic', [string]$InputDirectory,
      [string]$OutputDirectory, [string]$ObservationEnd,
      [ValidateSet('Auto','Docker','Portable')][string]$Backend = 'Auto', [switch]$OpenReport)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe') -or -not (Test-Path -LiteralPath '.env')) {
    & "$PSScriptRoot\setup.ps1" -Backend $Backend
} else {
    if ($Backend -eq 'Auto') { $Backend = if (Get-Command docker -ErrorAction SilentlyContinue) { 'Docker' } else { 'Portable' } }
    if ($Backend -eq 'Docker') { docker compose up -d --wait db }
    else { & .venv\Scripts\python.exe scripts\local_postgres.py start }
    if ($LASTEXITCODE -ne 0) { throw 'Database startup failed' }
}
if (-not $OutputDirectory) { $OutputDirectory = "output/demo/$Mode" }
$cliArguments = @('-m','retaillens','demo','--mode',$Mode,'--output',$OutputDirectory)
if ($InputDirectory) { $cliArguments += @('--input',$InputDirectory) }
if ($ObservationEnd) { $cliArguments += @('--observation-end',$ObservationEnd) }
& .venv\Scripts\python.exe @cliArguments
if ($LASTEXITCODE -ne 0) { throw 'RetailLens demo failed' }
if ($OpenReport) { & "$PSScriptRoot\open_powerbi.ps1" -Mode $Mode }
