param([switch]$Postgres, [string]$OutputDirectory = 'output/verification')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$logPath = [IO.Path]::GetFullPath((Join-Path $OutputDirectory 'verification.log'))
$utf8Encoding = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText($logPath, '', $utf8Encoding)
$results = [ordered]@{}
function Invoke-Check([string]$Name, [string[]]$Arguments) {
    [IO.File]::AppendAllText($logPath, "COMMAND: python $($Arguments -join ' ')`n", $utf8Encoding)
    & .venv\Scripts\python.exe @Arguments 2>&1 | ForEach-Object {
        $line = $_.ToString()
        Write-Output $line
        [IO.File]::AppendAllText($logPath, $line + [Environment]::NewLine, $utf8Encoding)
    }
    $code = $LASTEXITCODE
    [IO.File]::AppendAllText($logPath, "EXIT_CODE: $code`n", $utf8Encoding)
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
$json = $results | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText([IO.Path]::GetFullPath((Join-Path $OutputDirectory 'checks.json')), $json + "`n", $utf8Encoding)
if (@($results.Values | Where-Object {$_.status -eq 'FAIL'}).Count -gt 0) { exit 1 }
