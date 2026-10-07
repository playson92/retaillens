param(
    [string]$ModelPath,
    [string]$TomDirectory,
    [string]$Output,
    [switch]$Download
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $ModelPath) { $ModelPath = Join-Path $projectRoot 'powerbi/RetailLens.SemanticModel/definition' }
if (-not $TomDirectory) { $TomDirectory = Join-Path $projectRoot 'output/tools/tom-19.117.0/package/lib/net472' }
$version = '19.117.0'
$expectedHash = '6B29B095DE1C8562B711094433674EA56C13BEB1C707E1749DB6860A47C6F2B1'
$result = [ordered]@{ check = 'TMDL_PARSE'; status = 'NOT_RUN'; parser = 'Microsoft.AnalysisServices.Tabular.TmdlSerializer'; version = $version; runtime_validation = $false }
try {
    if (-not (Test-Path -LiteralPath $TomDirectory)) {
        if (-not $Download) { throw 'Pinned TOM parser is missing. Run scripts/parse_tmdl.ps1 -Download, or supply -TomDirectory with Microsoft.AnalysisServices 19.117.0 net472 assemblies.' }
        $toolsRoot = Join-Path $projectRoot 'output/tools/tom-19.117.0'
        New-Item -ItemType Directory -Path $toolsRoot -Force | Out-Null
        $archive = Join-Path $toolsRoot 'tom.zip'
        Invoke-WebRequest -Uri 'https://api.nuget.org/v3-flatcontainer/microsoft.analysisservices/19.117.0/microsoft.analysisservices.19.117.0.nupkg' -OutFile $archive -UseBasicParsing
        if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expectedHash) { throw 'TOM NuGet archive SHA256 mismatch.' }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead($archive)
        $destination = [IO.Path]::GetFullPath((Join-Path $toolsRoot 'package')) + [IO.Path]::DirectorySeparatorChar
        try {
            foreach ($entry in $zip.Entries) {
                $target = [IO.Path]::GetFullPath((Join-Path $destination $entry.FullName))
                if (-not $target.StartsWith($destination, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe path in TOM package.' }
            }
        } finally { $zip.Dispose() }
        Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $toolsRoot 'package') -Force
    }
    foreach ($name in @('Microsoft.AnalysisServices.Core.dll', 'Microsoft.AnalysisServices.Tabular.Json.dll', 'Microsoft.AnalysisServices.Tabular.dll')) {
        [Reflection.Assembly]::LoadFrom((Join-Path $TomDirectory $name)) | Out-Null
    }
    $database = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder([IO.Path]::GetFullPath($ModelPath))
    $moneyColumns = [ordered]@{}
    foreach ($table in $database.Model.Tables) {
        foreach ($column in $table.Columns) {
            if ($column.Name -in @('price','freight_value','item_value','expected_amount','paid_amount','payment_delta')) {
                if ($column.DataType -ne [Microsoft.AnalysisServices.Tabular.DataType]::Decimal) { throw "Money column must use TOM fixed Decimal: $($table.Name).$($column.Name)" }
                $moneyColumns["$($table.Name).$($column.Name)"] = $column.DataType.ToString()
            }
        }
    }
    $result.status = 'PASS'
    $result.tables = $database.Model.Tables.Count
    $result.measures = ($database.Model.Tables | ForEach-Object { $_.Measures.Count } | Measure-Object -Sum).Sum
    $result.relationships = $database.Model.Relationships.Count
    $result.expressions = $database.Model.Expressions.Count
    $result.compatibility_level = $database.CompatibilityLevel
    $result.money_columns = $moneyColumns
    $result.reason = 'Official TOM parser deserialized model metadata. DAX and Power Query are not executed by this check.'
} catch {
    $result.status = if (Test-Path -LiteralPath (Join-Path $TomDirectory 'Microsoft.AnalysisServices.Tabular.dll')) { 'FAIL' } else { 'NOT_RUN' }
    $result.reason = $_.Exception.ToString()
}
$json = $result | ConvertTo-Json -Depth 10
if ($Output) {
    $targetOutput = [IO.Path]::GetFullPath($Output)
    [IO.Directory]::CreateDirectory((Split-Path -Parent $targetOutput)) | Out-Null
    [IO.File]::WriteAllText($targetOutput, $json + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
}
Write-Output $json
if ($result.status -eq 'FAIL') { exit 1 }
if ($result.status -eq 'NOT_RUN') { exit 2 }
