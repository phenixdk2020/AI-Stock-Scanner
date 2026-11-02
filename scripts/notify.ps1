# B-13: Viser mandagslistens ændringer (data\aendringer.txt) som en Windows-besked.
# Kaldes af scripts\mandagsliste.cmd efter listen. Ingen besked, hvis intet har ændret sig.
param([string]$Fil = (Join-Path $PSScriptRoot '..\data\aendringer.txt'))
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Fil)) { exit 0 }
$linjer = @(Get-Content -Path $Fil -Encoding UTF8 | Where-Object { $_.Trim() })
if ($linjer.Count -eq 0) { exit 0 }
$tekst = ($linjer | Select-Object -First 6) -join "`n"
if ($linjer.Count -gt 6) { $tekst += "`n… og $($linjer.Count - 6) mere" }
try {
    [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
    [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $sikker = [System.Security.SecurityElement]::Escape($tekst)
    $xml.LoadXml("<toast><visual><binding template='ToastGeneric'><text>Mandagsliste: $($linjer.Count) ændringer</text><text>$sikker</text></binding></visual></toast>")
    $app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show((New-Object Windows.UI.Notifications.ToastNotification $xml))
} catch {
    Write-Output "Kunne ikke vise Windows-besked: $($_.Exception.Message)"
    Write-Output $tekst
}
