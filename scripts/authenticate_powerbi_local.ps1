param([Parameter(Mandatory=$true)][int]$DialogHandle, [Parameter(Mandatory=$true)][int]$ProcessId, [string]$SettingsPath = (Join-Path (Get-Location) '.env'), [switch]$NativeKeys)
$ErrorActionPreference = 'Stop'
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
if ($doc.getElementById('resourceKind').value -ne 'PostgreSQL' -or $doc.getElementById('resourcePath').value -ne '127.0.0.1:5433;retaillens') { throw 'Refusing credentials for a different data source.' }
$localSettings = @{}
foreach ($line in [IO.File]::ReadAllLines($SettingsPath)) {
    if ($line -match '^([A-Z_]+)=(.*)$') {
        $localSettings[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
    }
}
$databaseUser = [Environment]::GetEnvironmentVariable('DATABASE_USER')
$databasePassword = [Environment]::GetEnvironmentVariable('DATABASE_PASSWORD')
if (-not $databaseUser) { $databaseUser = $localSettings['DATABASE_USER'] }
if (-not $databasePassword) { $databasePassword = $localSettings['DATABASE_PASSWORD'] }
if (-not $databaseUser -or -not $databasePassword) { throw 'Existing local credentials are unavailable.' }
$usernameControl = $doc.getElementById('sqlusername')
$passwordControl = $doc.getElementById('sqlpassword')
if ($NativeKeys) {
    $activation = New-Object -ComObject WScript.Shell
    $activation.AppActivate($ProcessId) | Out-Null
    $foregroundPid = [uint32]0
    [RetailLensHtmlDialog]::GetWindowThreadProcessId([RetailLensHtmlDialog]::GetForegroundWindow(),[ref]$foregroundPid) | Out-Null
    if ($foregroundPid -ne $ProcessId) { throw 'Refusing keyboard input outside the authorized Desktop process.' }
    function ConvertTo-InputKeys([string]$text) {
        $builder = New-Object Text.StringBuilder
        foreach ($character in $text.ToCharArray()) {
            if ('+^%~(){}'.Contains([string]$character)) { [void]$builder.Append('{').Append($character).Append('}') }
            else { [void]$builder.Append($character) }
        }
        $builder.ToString()
    }
    $usernameControl.click() | Out-Null
    $usernameControl.focus() | Out-Null
    Start-Sleep -Milliseconds 200
    if ($doc.activeElement.id -ne 'sqlusername') { throw 'Username field does not own document focus.' }
    $activation.SendKeys('^a')
    Start-Sleep -Milliseconds 100
    $activation.SendKeys((ConvertTo-InputKeys $databaseUser))
    Start-Sleep -Milliseconds 300
    $passwordControl.click() | Out-Null
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
$connect.click() | Out-Null
$databaseUser = $null; $databasePassword = $null; $localSettings.Clear()
Write-Output 'Submitted existing credentials to the local PostgreSQL dialog; no credential values recorded.'
