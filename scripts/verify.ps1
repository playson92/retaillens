param([switch]$Postgres, [string]$OutputDirectory = 'output/verification')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$logPath = Join-Path $OutputDirectory 'verification.log'
$results = [ordered]@{}
function Invoke-Check([string]$Name, [string[]]$Arguments) {
    "COMMAND: python $($Arguments -join ' ')" | Out-File $logPath -Append -Encoding utf8
    & .venv\Scripts\python.exe @Arguments 2>&1 | Tee-Object -FilePath $logPath -Append
    $code = $LASTEXITCODE
    "EXIT_CODE: $code" | Out-File $logPath -Append -Encoding utf8
    $results[$Name] = @{status=$(if ($code -eq 0) {'PASS'} else {'FAIL'});exit_code=$code}
}
Invoke-Check 'RUFF_LINT' @('-m','ruff','check','.')
Invoke-Check 'RUFF_FORMAT' @('-m','ruff','format','--check','.')
Invoke-Check 'UNIT_TESTS' @('-m','pytest','-m','not integration','-p','no:cacheprovider','--basetemp',(Join-Path $OutputDirectory 'unit_tmp'))
if ($Postgres) {
    $env:RETAILLENS_TEST_POSTGRES = '1'
    Invoke-Check 'POSTGRES_INTEGRATION' @('-m','pytest','-m','integration','-p','no:cacheprovider','--basetemp',(Join-Path $OutputDirectory 'integration_tmp'))
    Remove-Item Env:\RETAILLENS_TEST_POSTGRES
} else { $results['POSTGRES_INTEGRATION'] = @{status='NOT_RUN';reason='Pass -Postgres to run against local fixture schema'} }
Invoke-Check 'PBIP_SCHEMA' @('scripts/validate_powerbi.py','--output',(Join-Path $OutputDirectory 'pbip_validation.json'))
$results | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $OutputDirectory 'checks.json')
if (@($results.Values | Where-Object {$_.status -eq 'FAIL'}).Count -gt 0) { exit 1 }
