param(
    [string]$RunDirectory,
    [ValidateRange(1024,65535)][int]$Port = 6433,
    [string]$DockerContext = 'desktop-linux',
    [string]$DockerPath
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts/setup.ps1 -Backend Portable first.' }
    if (-not $DockerPath) {
        $candidates = @(
            (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'),
            'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
        )
        $DockerPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $DockerPath) { throw 'Installed Docker Desktop CLI not found; pass -DockerPath explicitly.' }
    }
    if (-not (Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue)) {
        $desktop = Join-Path (Split-Path (Split-Path (Split-Path $DockerPath -Parent) -Parent) -Parent) 'Docker Desktop.exe'
        if (Test-Path -LiteralPath $desktop) { Start-Process -FilePath $desktop -WindowStyle Hidden }
    }
    $arguments = @('scripts/verify_docker.py','--docker',$DockerPath,'--context',$DockerContext,'--port',"$Port")
    if ($RunDirectory) { $arguments += @('--run',$RunDirectory) }
    & $python @arguments
    $result = $LASTEXITCODE
} finally { Pop-Location }
exit $result
