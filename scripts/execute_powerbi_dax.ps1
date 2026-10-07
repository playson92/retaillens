param(
    [Parameter(Mandatory=$true)][string]$Server,
    [Parameter(Mandatory=$true)][string]$Catalog,
    [Parameter(Mandatory=$true)][string]$Queries,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference = 'Stop'
if ($Server -notmatch '^localhost:\d+$') { throw 'Runtime queries are restricted to the local Desktop engine.' }
$clientPath = Join-Path (Get-Location) 'output\tools\adomd-19.117.0\package\lib\net472\Microsoft.AnalysisServices.AdomdClient.dll'
[Reflection.Assembly]::LoadFrom($clientPath) | Out-Null
$connection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=$Server;Initial Catalog=$Catalog")
$connection.Open()
$results = New-Object Collections.Generic.List[object]
try {
    $requests = [IO.File]::ReadAllText([IO.Path]::GetFullPath($Queries)) | ConvertFrom-Json
    foreach ($request in $requests) {
        $watch = [Diagnostics.Stopwatch]::StartNew()
        $command = $connection.CreateCommand()
        $command.CommandTimeout = 90
        $command.CommandText = $request.dax
        try {
            $reader = $command.ExecuteReader()
            $rows = New-Object Collections.Generic.List[object]
            while ($reader.Read()) {
                $row = [ordered]@{}
                for ($i=0; $i -lt $reader.FieldCount; $i++) {
                    $value = $reader.GetValue($i)
                    if ($value -is [DBNull]) { $value = $null }
                    elseif ($value -is [decimal]) { $value = $value.ToString([Globalization.CultureInfo]::InvariantCulture) }
                    elseif ($value -is [DateTime]) { $value = $value.ToString('o') }
                    $row[$reader.GetName($i)] = $value
                }
                $rows.Add($row)
            }
            $reader.Close()
            $results.Add([ordered]@{ id=$request.id; status='PASS_EXECUTED'; dax=$request.dax; rows=$rows.ToArray(); elapsed_ms=$watch.ElapsedMilliseconds })
        } catch {
            $results.Add([ordered]@{ id=$request.id; status='FAIL'; dax=$request.dax; error=$_.Exception.Message; elapsed_ms=$watch.ElapsedMilliseconds })
        }
    }
} finally { $connection.Close() }
$artifact = [ordered]@{ checked_at_utc=[DateTime]::UtcNow.ToString('o'); client_version='19.117.0'; server=$Server; catalog=$Catalog; results=$results.ToArray() }
[IO.File]::WriteAllText([IO.Path]::GetFullPath($Output),($artifact|ConvertTo-Json -Depth 20),(New-Object Text.UTF8Encoding($false)))
$failed = @($results | Where-Object { $_.status -eq 'FAIL' })
Write-Output "Executed $($results.Count) actual Desktop DAX queries; execution errors: $($failed.Count); evidence $Output"
if ($failed.Count) { exit 1 }
