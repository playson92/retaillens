param([ValidateSet('Auto','Docker','Portable')][string]$Backend = 'Auto', [string]$Python)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    $candidates = @($Python, "$env:LOCALAPPDATA\Python\pythoncore-3.12-64\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe")
    $selected = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    if (-not $selected) { throw 'Python 3.12 is required. Pass -Python with its executable path.' }
    & $selected -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
}
& .venv\Scripts\python.exe -c 'import sys; assert sys.version_info[:2] == (3,12)'
if ($LASTEXITCODE -ne 0) { throw 'Existing environment must use Python 3.12' }
& .venv\Scripts\python.exe -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& .venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Project installation failed' }
& .venv\Scripts\python.exe -c 'from scripts.local_postgres import private_env; private_env()'
if ($LASTEXITCODE -ne 0) { throw 'Local configuration failed' }
if ($Backend -eq 'Auto') { $Backend = if (Get-Command docker -ErrorAction SilentlyContinue) { 'Docker' } else { 'Portable' } }
if ($Backend -eq 'Docker') {
    & .venv\Scripts\python.exe scripts\check_port.py
    if ($LASTEXITCODE -ne 0) { throw 'Port check failed' }
    docker compose up -d --wait db
} else { & .venv\Scripts\python.exe scripts\local_postgres.py start }
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed' }
Write-Output "Setup ready ($Backend); run .\scripts\demo.ps1"
