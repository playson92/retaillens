param([Parameter(Mandatory=$true)][int]$ProcessId, [Parameter(Mandatory=$true)][ValidateSet('rl_real','rl_synthetic')][string]$Schema, [string]$SettingsPath = (Join-Path (Get-Location) '.env'))
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'powerbi_source_guard.ps1')
$process = Get-Process -Id $ProcessId
if ($process.ProcessName -ne 'PBIDesktop') { throw 'Target must be the authorized Power BI Desktop process.' }
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$source = [IO.File]::ReadAllText((Join-Path (Get-Location) 'scripts\authenticate_powerbi_local.ps1'))
$start = $source.IndexOf("Add-Type @'")
Invoke-Expression $source.Substring($start,$source.IndexOf("'@")+2-$start)
$expected = Get-RetailLensPowerBIConnection -SettingsPath $SettingsPath
$approved = 0
for ($attempt=0; $attempt -lt 12; $attempt++) {
    $roots = [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children,(New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty,$ProcessId)))
    $doc = $null
    foreach ($root in $roots) {
        $ies = @($root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition) | Where-Object { $_.Current.ClassName -eq 'Internet Explorer_Server' -and -not $_.Current.IsOffscreen })
        foreach ($ie in $ies) {
            try { $candidateDoc = [RetailLensHtmlDialog]::Document([IntPtr]$ie.Current.NativeWindowHandle) }
            catch {
                $inner = $_.Exception
                while ($inner.InnerException) { $inner = $inner.InnerException }
                if ($inner.HResult -eq -2147467259) { continue } # A closing MSHTML dialog no longer exposes a document.
                throw
            }
            $candidateBody = [string]$candidateDoc.body.innerText
            if ([regex]::IsMatch($candidateBody,'(?m)^SELECT [^\r\n]+')) {
                if (-not (Test-RetailLensQuerySource -Body $candidateBody -Schema $Schema -ExpectedPath $expected.resource_path)) { throw 'Prompt is not a reviewed read-only query for the authorized local warehouse.' }
                $doc = $candidateDoc
                $body = $candidateBody
                break
            }
        }
        if ($doc) { break }
    }
    if (-not $doc) { break }
    $sql = [regex]::Match($body,'(?m)^SELECT [^\r\n]+').Value.Trim()
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
