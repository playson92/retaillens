param([Parameter(Mandatory=$true)][int]$DialogHandle, [Parameter(Mandatory=$true)][int]$ProcessId, [string]$SettingsPath = (Join-Path (Get-Location) '.env'), [switch]$NativeKeys)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'powerbi_source_guard.ps1')
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class RetailLensHtmlDialog {
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern uint RegisterWindowMessage(string name);
 [DllImport("user32.dll",SetLastError=true)] public static extern IntPtr SendMessageTimeout(IntPtr h,uint msg,IntPtr wp,IntPtr lp,uint flags,uint timeout,out IntPtr result);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint process);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("oleacc.dll")] public static extern int ObjectFromLresult(IntPtr result,ref Guid iid,IntPtr wp,[MarshalAs(UnmanagedType.Interface)] out object obj);
 public static object Document(IntPtr hwnd) {
   IntPtr result;
   SendMessageTimeout(hwnd,RegisterWindowMessage("WM_HTML_GETOBJECT"),IntPtr.Zero,IntPtr.Zero,2,3000,out result);
   var iid=new Guid("332C4425-26CB-11D0-B483-00C04FD90119");
   object o; int hr=ObjectFromLresult(result,ref iid,IntPtr.Zero,out o);
   if(hr!=0) Marshal.ThrowExceptionForHR(hr); return o;
 }
}
'@
$ownerPid = [uint32]0
[RetailLensHtmlDialog]::GetWindowThreadProcessId([IntPtr]$DialogHandle,[ref]$ownerPid) | Out-Null
if ($ownerPid -ne $ProcessId -or (Get-Process -Id $ProcessId).ProcessName -ne 'PBIDesktop') { throw 'Credential control must belong to the authorized Desktop process.' }
$doc = [RetailLensHtmlDialog]::Document([IntPtr]$DialogHandle)
$expected = Get-RetailLensPowerBIConnection -SettingsPath $SettingsPath
if (-not (Test-RetailLensCredentialSource -ResourceKind $doc.getElementById('resourceKind').value -ResourcePath $doc.getElementById('resourcePath').value -ExpectedPath $expected.resource_path)) { throw 'Refusing credentials for a different data source.' }
$connection = Get-RetailLensPowerBIConnection -SettingsPath $SettingsPath -Credentials
if ($connection.resource_path -cne $expected.resource_path) { throw 'Connection configuration changed during authentication.' }
$databaseUser = $connection.user
$databasePassword = $connection.password
if (-not $databaseUser -or -not $databasePassword) { throw 'Existing local credentials are unavailable.' }
$usernameControl = $doc.getElementById('sqlusername')
$passwordControl = $doc.getElementById('sqlpassword')
# Native credential edits need normal focus changes and the real submit button;
# DOM click alone can retain an empty password despite matching input values.
Add-Type @'
using System; using System.Runtime.InteropServices;
public class RetailLensNativeFieldClick {
 [StructLayout(LayoutKind.Sequential)] public struct Point { public int X,Y; }
 [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h,ref Point p);
 [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(Point p);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr e);
 [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr c);
}
'@
function Click-OwnedCredentialControl($control) {
 $foreground=[uint32]0
 [RetailLensHtmlDialog]::GetWindowThreadProcessId([RetailLensHtmlDialog]::GetForegroundWindow(),[ref]$foreground) | Out-Null
 if($foreground -ne $ProcessId){throw 'Refusing native click outside owned Desktop'}
 [RetailLensNativeFieldClick]::SetThreadDpiAwarenessContext([IntPtr](-4)) | Out-Null
 $r=New-Object RetailLensNativeFieldClick+Rect
 if(![RetailLensNativeFieldClick]::GetClientRect([IntPtr]$DialogHandle,[ref]$r)){throw 'No source form client bounds'}
 $b=$control.getBoundingClientRect()
 $p=New-Object RetailLensNativeFieldClick+Point
 $p.X=[int](($b.left+$b.right)/2*($r.Right-$r.Left)/$doc.documentElement.clientWidth)
 $p.Y=[int](($b.top+$b.bottom)/2*($r.Bottom-$r.Top)/$doc.documentElement.clientHeight)
 if(![RetailLensNativeFieldClick]::ClientToScreen([IntPtr]$DialogHandle,[ref]$p)){throw 'No screen point'}
 $target=[RetailLensNativeFieldClick]::WindowFromPoint($p)
 $targetPid=[uint32]0;[RetailLensHtmlDialog]::GetWindowThreadProcessId($target,[ref]$targetPid) | Out-Null
 if($targetPid -ne $ProcessId -or $target -ne [IntPtr]$DialogHandle){throw 'Refusing click into an occluded source field'}
 [RetailLensNativeFieldClick]::SetCursorPos($p.X,$p.Y) | Out-Null
 [RetailLensNativeFieldClick]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
 [RetailLensNativeFieldClick]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 300
}

if ($NativeKeys) {
    $activation = New-Object -ComObject WScript.Shell
    $activation.AppActivate($ProcessId) | Out-Null
    $foregroundPid = [uint32]0
    for ($attempt=0; $attempt -lt 10; $attempt++) {
        [RetailLensHtmlDialog]::GetWindowThreadProcessId([RetailLensHtmlDialog]::GetForegroundWindow(),[ref]$foregroundPid) | Out-Null
        if ($foregroundPid -eq $ProcessId) { break }
        Start-Sleep -Milliseconds 200
    }
    if ($foregroundPid -ne $ProcessId) { throw 'Refusing keyboard input outside the authorized Desktop process.' }
    function ConvertTo-InputKeys([string]$text) {
        $builder = New-Object Text.StringBuilder
        foreach ($character in $text.ToCharArray()) {
            if ('+^%~(){}'.Contains([string]$character)) { [void]$builder.Append('{').Append($character).Append('}') }
            else { [void]$builder.Append($character) }
        }
        $builder.ToString()
    }
    function Wait-OwnedCredentialInput([string]$id,[string]$wanted) {
        for($attempt=0;$attempt -lt 25;$attempt++){
            $owner=[uint32]0
            [RetailLensHtmlDialog]::GetWindowThreadProcessId([RetailLensHtmlDialog]::GetForegroundWindow(),[ref]$owner) | Out-Null
            if($owner -ne $ProcessId){throw 'Refusing input processing outside the authorized Desktop process.'}
            if($doc.getElementById($id).value -ceq $wanted){return}
            Start-Sleep -Milliseconds 200
        }
        throw 'Credential field did not retain the submitted input within the processing timeout.'
    }
    Click-OwnedCredentialControl $usernameControl
    $usernameControl.focus() | Out-Null
    Start-Sleep -Milliseconds 200
    if ($doc.activeElement.id -ne 'sqlusername') { throw 'Username field does not own document focus.' }
    $activation.SendKeys('^a')
    Start-Sleep -Milliseconds 100
    $activation.SendKeys((ConvertTo-InputKeys $databaseUser))
    Start-Sleep -Milliseconds 300
    Click-OwnedCredentialControl $passwordControl
    $passwordControl = $doc.getElementById('sqlpassword')
    $passwordControl.focus() | Out-Null
    Start-Sleep -Milliseconds 200
    if ($doc.activeElement.id -ne 'sqlpassword') { throw 'Password field does not own document focus.' }
    [RetailLensHtmlDialog]::GetWindowThreadProcessId([RetailLensHtmlDialog]::GetForegroundWindow(),[ref]$foregroundPid) | Out-Null
    if ($foregroundPid -ne $ProcessId) { throw 'Refusing password input outside the authorized Desktop process.' }
    $activation.SendKeys('^a')
    Start-Sleep -Milliseconds 100
    $activation.SendKeys((ConvertTo-InputKeys $databasePassword))
    Start-Sleep -Milliseconds 300
} else {
# Desktop's native credential form marks a password as edited from its normal
# click handler. Setting DOM value alone leaves the original empty password.
$usernameControl.click() | Out-Null
$passwordControl.click() | Out-Null
$usernameControl = $doc.getElementById('sqlusername')
$passwordControl = $doc.getElementById('sqlpassword')
$passwordControl.focus() | Out-Null
$usernameControl.fireEvent('onkeydown') | Out-Null
$passwordControl.fireEvent('onkeydown') | Out-Null
$usernameControl.value = $databaseUser
$passwordControl.value = $databasePassword
if ($doc.getElementById('sqlusername').value -ne $databaseUser -or $doc.getElementById('sqlpassword').value -ne $databasePassword) { throw ('Credential UI did not retain submitted input; username matched: {0}; password matched: {1}; focused field: {2}.' -f ($doc.getElementById('sqlusername').value -eq $databaseUser),($doc.getElementById('sqlpassword').value -eq $databasePassword),$doc.activeElement.id) }
$usernameControl.fireEvent('oninput') | Out-Null
$passwordControl.fireEvent('oninput') | Out-Null
$usernameControl.fireEvent('onkeyup') | Out-Null
$passwordControl.fireEvent('onkeyup') | Out-Null
$usernameControl.fireEvent('onchange') | Out-Null
$passwordControl.fireEvent('onchange') | Out-Null
$usernameControl.fireEvent('onblur') | Out-Null
$passwordControl.fireEvent('onblur') | Out-Null
}
if ($doc.getElementById('sqlusername').value -ne $databaseUser -or $doc.getElementById('sqlpassword').value -ne $databasePassword) { throw 'Credential UI did not retain the submitted input.' }
$connect = $null
for ($i=0; $i -lt $doc.all.length; $i++) {
    $candidate = $doc.all.item($i)
    if ([string]$candidate.className -match '(^|\s)ng-challenge-ok(\s|$)') { $connect = $candidate; break }
}
if (-not $connect) { throw 'Authorized database authentication button is unavailable.' }
if($NativeKeys){
    [RetailLensHtmlDialog]::GetWindowThreadProcessId([RetailLensHtmlDialog]::GetForegroundWindow(),[ref]$foregroundPid) | Out-Null
    if($foregroundPid -ne $ProcessId){throw 'Refusing field commit outside owned Desktop'}
    $activation.SendKeys('{TAB}')
    Start-Sleep -Milliseconds 600
    Click-OwnedCredentialControl $connect
}else{$connect.click() | Out-Null}
$databaseUser = $null; $databasePassword = $null; $connection = $null
Write-Output 'Submitted existing credentials to the local PostgreSQL dialog; no credential values recorded.'
