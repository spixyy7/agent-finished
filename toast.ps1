# Shows one Windows toast. Text comes in through environment variables so
# quotes and non-ASCII letters survive: FIN_TITLE, FIN_BODY, FIN_ICON.
# Runs under Windows PowerShell 5.1 (powershell.exe), which still has WinRT.
$ErrorActionPreference = 'Stop'
$appId = 'Agents.Finished'
$key = "HKCU:\Software\Classes\AppUserModelId\$appId"
if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
Set-ItemProperty -Path $key -Name DisplayName -Value 'Agents'
if ($env:FIN_ICON -and (Test-Path $env:FIN_ICON)) {
    Set-ItemProperty -Path $key -Name IconUri -Value $env:FIN_ICON
}

[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$title = [Security.SecurityElement]::Escape($env:FIN_TITLE)
$body = [Security.SecurityElement]::Escape($env:FIN_BODY)
$img = ''
if ($env:FIN_ICON -and (Test-Path $env:FIN_ICON)) {
    $src = [Security.SecurityElement]::Escape(([Uri]$env:FIN_ICON).AbsoluteUri)
    $img = "<image placement='appLogoOverride' hint-crop='circle' src='$src'/>"
}
$xml = "<toast><visual><binding template='ToastGeneric'><text>$title</text><text>$body</text>$img</binding></visual><audio silent='true'/></toast>"

$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
$toast.Tag = 'f' + [DateTime]::Now.Ticks.ToString().Substring(8)
$toast.Group = 'finished'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
