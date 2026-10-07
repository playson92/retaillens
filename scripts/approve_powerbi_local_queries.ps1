param([Parameter(Mandatory=$true)][int]$ProcessId, [Parameter(Mandatory=$true)][ValidateSet('rl_real','rl_synthetic')][string]$Schema)
$ErrorActionPreference = 'Stop'
$process = Get-Process -Id $ProcessId
if ($process.ProcessName -ne 'PBIDesktop') { throw 'Target must be the authorized Power BI Desktop process.' }
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$source = [IO.File]::ReadAllText((Join-Path (Get-Location) 'scripts\authenticate_powerbi_local.ps1'))
$start = $source.IndexOf("Add-Type @'")
Invoke-Expression $source.Substring($start,$source.IndexOf("'@")+2-$start)
$approved = 0
for ($attempt=0; $attempt -lt 12; $attempt++) {
    $roots = [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children,(New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty,$ProcessId)))
    $ies = @($roots[0].FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition) | Where-Object { $_.Current.ClassName -eq 'Internet Explorer_Server' })
    if (-not $ies.Count) { break }
    $doc = [RetailLensHtmlDialog]::Document([IntPtr]$ies[0].Current.NativeWindowHandle)
    $body = [string]$doc.body.innerText
    $sql = [regex]::Match($body,'(?m)^SELECT [^\r\n]+').Value.Trim()
    if (-not $body.Contains('127.0.0.1:5433;retaillens') -or $sql -notmatch ('^SELECT [^;]+ FROM '+$Schema+'\.(mart_orders|mart_items|dim_date|dim_product|dim_seller|mart_cohorts|quality_summary|run_metadata)$')) { throw 'Prompt is not a reviewed read-only query for the authorized local warehouse.' }
    $button = $null
    for ($i=0; $i -lt $doc.all.length; $i++) {
        $candidate = $doc.all.item($i)
        if ([string]$candidate.className -match '(^|\s)js-ok(\s|$)') { $button = $candidate; break }
    }
    if (-not $button) { throw 'Native query confirmation button is unavailable.' }
    $button.click() | Out-Null
    $approved++
    Write-Output "Approved normal Desktop UI prompt for reviewed local SELECT: $sql"
    Start-Sleep -Milliseconds 700
}
Write-Output "Approved $approved read-only native query prompts; global approval settings were not changed."
