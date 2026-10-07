param(
    [Parameter(Mandatory=$true)][int]$ProcessId,
    [Parameter(Mandatory=$true)][string]$StartDate,
    [Parameter(Mandatory=$true)][string]$EndDate
)
$ErrorActionPreference = 'Stop'
$start = [DateTime]::ParseExact($StartDate,'yyyy-MM-dd',[Globalization.CultureInfo]::InvariantCulture)
$end = [DateTime]::ParseExact($EndDate,'yyyy-MM-dd',[Globalization.CultureInfo]::InvariantCulture)
if ($end -lt $start) { throw 'Report dates must form a valid inclusive interval.' }
if ((Get-Process -Id $ProcessId).ProcessName -ne 'PBIDesktop') { throw 'Expected the explicitly owned Desktop process.' }
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$roots = [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children,(New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty,$ProcessId)))
$all = $roots[0].FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
$activation = New-Object -ComObject WScript.Shell
$activation.AppActivate($ProcessId) | Out-Null
$endLabel = 'Data zako'+[char]0x0144+'czenia.'
$startLabel = 'Data rozpocz'+[char]0x0119+'cia.'
foreach ($entry in @(@($endLabel,$EndDate),@($startLabel,$StartDate))) {
    $matches = @($all | Where-Object { $_.Current.ControlType -eq [Windows.Automation.ControlType]::Edit -and $_.Current.Name.StartsWith($entry[0]) -and -not $_.Current.IsOffscreen })
    if ($matches.Count -ne 1) { throw 'Expected exactly one visible date input in the owned report.' }
    $matches[0].SetFocus()
    Start-Sleep -Milliseconds 200
    if (-not $matches[0].Current.HasKeyboardFocus) { throw 'Date input does not have keyboard focus; no keys sent.' }
    $activation.SendKeys('^a')
    Start-Sleep -Milliseconds 100
    $activation.SendKeys($entry[1])
    $activation.SendKeys('{TAB}')
    Start-Sleep -Milliseconds 400
}
Write-Output "Entered actual report date interval $StartDate through $EndDate (inclusive)."
