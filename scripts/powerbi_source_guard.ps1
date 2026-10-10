function Get-RetailLensPowerBIConnection {
    param([string]$SettingsPath, [switch]$Credentials)
    $root = Split-Path $PSScriptRoot -Parent
    $python = Join-Path $root '.venv\Scripts\python.exe'
    $resolver = Join-Path $root 'scripts\resolve_powerbi_connection.py'
    $arguments = @($resolver, '--settings', [IO.Path]::GetFullPath($SettingsPath))
    if ($Credentials) { $arguments += '--credentials' }
    $privateResult = & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve the authorized local PostgreSQL source.' }
    $connection = $privateResult | ConvertFrom-Json
    $privateResult = $null
    return $connection
}

function Test-RetailLensCredentialSource {
    param([string]$ResourceKind, [string]$ResourcePath, [string]$ExpectedPath)
    return ($ResourceKind -ceq 'PostgreSQL' -and $ResourcePath -ceq $ExpectedPath)
}

function Test-RetailLensQuerySource {
    param([string]$Body, [string]$Schema, [string]$ExpectedPath)
    if ($Schema -notin @('rl_real','rl_synthetic')) { return $false }
    $sourcePattern = '(?<![A-Za-z0-9_.:;-])'+[regex]::Escape($ExpectedPath)+'(?![A-Za-z0-9_.:;-])'
    $queries = [regex]::Matches($Body,'(?m)^SELECT [^\r\n]+')
    if (-not [regex]::IsMatch($Body,$sourcePattern) -or $queries.Count -ne 1) { return $false }
    return ($queries[0].Value.Trim() -cmatch ('^SELECT [^;]+ FROM '+$Schema+'\.(mart_orders|mart_items|dim_date|dim_product|dim_seller|mart_cohorts|quality_summary|run_metadata)$'))
}
