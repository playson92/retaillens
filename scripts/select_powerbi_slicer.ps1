param(
    [Parameter(Mandatory=$true)][int]$ProcessId,
    [Parameter(Mandatory=$true)][ValidateSet('category','seller_id','order_id','reconciliation_status','customer_state','is_on_time')][string]$Field,
    [Parameter(Mandatory=$true)][string]$Value
)
$ErrorActionPreference = 'Stop'
if ((Get-Process -Id $ProcessId).ProcessName -ne 'PBIDesktop') { throw 'Expected the explicitly owned Desktop process.' }
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$roots = [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children,(New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty,$ProcessId)))
$combos = @()
for ($attempt=0; $attempt -lt 6; $attempt++) {
    $all = $roots[0].FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
    $combos = @($all | Where-Object { $_.Current.ControlType -eq [Windows.Automation.ControlType]::ComboBox -and $_.Current.Name -eq $Field -and -not $_.Current.IsOffscreen })
    if ($combos.Count -eq 1) { break }
    Start-Sleep -Milliseconds 300
}
if ($combos.Count -ne 1) { throw 'Expected exactly one visible native slicer for the selected field.' }
$expand = $combos[0].GetCurrentPattern([Windows.Automation.ExpandCollapsePattern]::Pattern)
$expand.Expand()
Start-Sleep -Milliseconds 250
$all = $roots[0].FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
$choices = @($all | Where-Object { $_.Current.ControlType -eq [Windows.Automation.ControlType]::ListItem -and $_.Current.Name -eq $Value -and -not $_.Current.IsOffscreen })
if ($choices.Count -ne 1) { throw 'Expected exactly one visible native slicer value; no selection made.' }
$toggle = $null
if (-not $choices[0].TryGetCurrentPattern([Windows.Automation.TogglePattern]::Pattern,[ref]$toggle) -or $toggle.Current.ToggleState -ne [Windows.Automation.ToggleState]::On) {
    $invoke = $choices[0].GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern)
    $invoke.Invoke()
}
$expand.Collapse()
Start-Sleep -Milliseconds 600
$combos[0].SetFocus()
$activation = New-Object -ComObject WScript.Shell
$activation.AppActivate($ProcessId) | Out-Null
if (-not $combos[0].Current.HasKeyboardFocus) { throw 'Slicer does not have keyboard focus; no dismissal key sent.' }
$activation.SendKeys('{ESC}')
Start-Sleep -Milliseconds 250
Write-Output "Selected actual report slicer $Field = $Value."
