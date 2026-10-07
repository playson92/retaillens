param(
    [Parameter(Mandatory=$true)][int]$ProcessId,
    [Parameter(Mandatory=$true)][string]$ProjectPath
)
$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath($ProjectPath)
$allowedRoot = [IO.Path]::GetFullPath((Join-Path (Get-Location) 'output\powerbi')) + '\'
if (-not $project.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetExtension($project) -ne '.pbip') { throw 'Only this project''s private runtime copies may be closed.' }
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId"
if ($process.Name -ne 'PBIDesktop.exe' -or $process.CommandLine.IndexOf($project,[StringComparison]::OrdinalIgnoreCase) -lt 0) { throw 'Process command line does not match the explicitly owned private project.' }
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$condition = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty,$ProcessId)
$roots = [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children,$condition)
$roots[0].GetCurrentPattern([Windows.Automation.WindowPattern]::Pattern).Close()
Start-Sleep -Milliseconds 300
if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
    $ies = @()
    for ($attempt=0; $attempt -lt 8; $attempt++) {
        if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) { break }
        $roots = [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children,$condition)
        $ies = @($roots[0].FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition) | Where-Object { $_.Current.ClassName -eq 'Internet Explorer_Server' })
        if ($ies.Count -eq 1) { break }
        Start-Sleep -Milliseconds 350
    }
    if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) { Write-Output 'Private baseline report closed without a save prompt.'; return }
    if ($ies.Count -ne 1) { throw 'Expected the normal private-report save confirmation.' }
    $source = [IO.File]::ReadAllText((Join-Path (Get-Location) 'scripts\authenticate_powerbi_local.ps1'))
    $start = $source.IndexOf("Add-Type @'")
    Invoke-Expression $source.Substring($start,$source.IndexOf("'@")+2-$start)
    $doc = [RetailLensHtmlDialog]::Document([IntPtr]$ies[0].Current.NativeWindowHandle)
    $saveQuestion = 'Czy chcesz zapisa'+[char]0x0107+' zmiany?'
    if (-not $doc.body.innerText.Contains($saveQuestion)) { throw 'Unexpected dialog; no confirmation clicked.' }
    $discard = $null
    for ($i=0; $i -lt $doc.all.length; $i++) {
        $candidate = $doc.all.item($i)
        if ([string]$candidate.className -match 'o-action-button' -and $candidate.innerText -eq 'Nie zapisuj') { $discard=$candidate; break }
    }
    if (-not $discard) { throw 'Normal do-not-save button is unavailable.' }
    $discard.click() | Out-Null
}
Write-Output 'Closed only the explicitly owned baseline private report without saving cache or view changes.'
