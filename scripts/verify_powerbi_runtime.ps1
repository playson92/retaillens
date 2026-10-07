param(
    [ValidateSet('Inspect','Screenshot','Invoke')][string]$Action = 'Inspect',
    [Parameter(Mandatory=$true)][int]$ProcessId,
    [string]$Name,
    [string]$AutomationId,
    [int]$Index = -1,
    [string]$Output,
    [int]$Limit = 600
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class RetailLensDesktopWindow {
    [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out Rect rect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd, int command);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint process);
}
'@
$process = Get-Process -Id $ProcessId
if ($process.ProcessName -ne 'PBIDesktop') { throw 'Target must be the authorized Power BI Desktop process.' }
$root = [Windows.Automation.AutomationElement]::RootElement
$condition = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty,$ProcessId)
$windows = $root.FindAll([Windows.Automation.TreeScope]::Children,$condition)
if (-not $windows.Count) { throw 'Power BI window is unavailable to this UIAutomation execution context.' }
$window = $windows | Where-Object { $_.Current.NativeWindowHandle -eq $process.MainWindowHandle } | Select-Object -First 1
if (-not $window) { $window = $windows[0] }
$elements = if ($Action -ne 'Screenshot') { $window.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition) } else { $null }
if ($Action -eq 'Inspect') {
    $rows = @()
    $index = 0
    foreach ($element in $elements) {
        if ($index -ge $Limit) { break }
        $invoke = $null; $value = $null; $selection = $null
        $rows += [ordered]@{
            index = $index
            name = $element.Current.Name
            automation_id = $element.Current.AutomationId
            control = $element.Current.ControlType.ProgrammaticName
            class = $element.Current.ClassName
            enabled = $element.Current.IsEnabled
            offscreen = $element.Current.IsOffscreen
            bounds = $element.Current.BoundingRectangle.ToString()
            invoke = $element.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$invoke)
            editable = $element.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$value)
            selectable = $element.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$selection)
        }
        $index++
    }
    $result = [ordered]@{ process_id = $ProcessId; title = $window.Current.Name; handle = $window.Current.NativeWindowHandle; elements = $rows }
    $json = $result | ConvertTo-Json -Depth 8
    if ($Output) {
        [IO.File]::WriteAllText([IO.Path]::GetFullPath($Output),$json,(New-Object Text.UTF8Encoding($false)))
        Write-Output "Inspected $($rows.Count) Power BI controls; title '$($window.Current.Name)'; snapshot $Output"
    } else { Write-Output $json }
} elseif ($Action -eq 'Screenshot') {
    if (-not $Output) { throw 'Output PNG path is required.' }
    $handle = [IntPtr]$window.Current.NativeWindowHandle
    [RetailLensDesktopWindow]::ShowWindow($handle,3) | Out-Null
    try { $window.SetFocus() } catch { }
    $activation = New-Object -ComObject WScript.Shell
    $activation.AppActivate($ProcessId) | Out-Null
    [RetailLensDesktopWindow]::SetForegroundWindow($handle) | Out-Null
    Start-Sleep -Milliseconds 750
    $foregroundPid = [uint32]0
    [RetailLensDesktopWindow]::GetWindowThreadProcessId([RetailLensDesktopWindow]::GetForegroundWindow(),[ref]$foregroundPid) | Out-Null
    if ($foregroundPid -ne $ProcessId) { throw 'Power BI is not foreground; refusing screen capture of other applications.' }
    $rect = New-Object RetailLensDesktopWindow+Rect
    if (-not [RetailLensDesktopWindow]::GetWindowRect($handle,[ref]$rect)) { throw 'Cannot determine Power BI window bounds.' }
    # Copy only the foreground Power BI rectangle inside the screen. GPU-backed
    # WebView may return a black bitmap from PrintWindow despite a successful call.
    $screen = [Windows.Forms.Screen]::FromHandle($handle).Bounds
    $left = [Math]::Max($screen.Left,$rect.Left); $top = [Math]::Max($screen.Top,$rect.Top)
    $width = [Math]::Min($screen.Right,$rect.Right)-$left; $height = [Math]::Min($screen.Bottom,$rect.Bottom)-$top
    [RetailLensDesktopWindow]::SetCursorPos($left+[int]($width/2),$top+20) | Out-Null
    Start-Sleep -Milliseconds 400
    $bitmap = New-Object Drawing.Bitmap($width,$height)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen($left,$top,0,0,$bitmap.Size)
        $bitmap.Save([IO.Path]::GetFullPath($Output),[Drawing.Imaging.ImageFormat]::Png)
    } finally { $graphics.Dispose(); $bitmap.Dispose() }
    Write-Output "Captured only Power BI window to $Output"
} else {
    if (-not $Name -and -not $AutomationId) { throw 'Name or AutomationId is required.' }
    $candidates = if ($Index -ge 0) { @($elements[$Index]) } else { @($elements) }
    $matches = @($candidates | Where-Object { (-not $Name -or $_.Current.Name -eq $Name) -and (-not $AutomationId -or $_.Current.AutomationId -eq $AutomationId) -and $_.Current.IsEnabled -and -not $_.Current.IsOffscreen })
    if ($matches.Count -ne 1) { throw "Expected exactly one visible matching control, found $($matches.Count)." }
    $pattern = $null
    if ($matches[0].TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)) { $pattern.Invoke() }
    elseif ($matches[0].TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern)) { $pattern.Select() }
    elseif ($matches[0].TryGetCurrentPattern([Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$pattern)) { $pattern.Expand() }
    else { throw 'Control has no Invoke/SelectionItem pattern; no action taken.' }
    Write-Output "Invoked Power BI control $Name $AutomationId"
}
