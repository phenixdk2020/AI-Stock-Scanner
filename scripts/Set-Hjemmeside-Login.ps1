# Gemmer login til aktier.hangar18.dk, så mandagslisten automatisk opdaterer hjemmesiden.
# Du indtaster selv brugernavn og et WordPress Application Password (Profil > Application Passwords).
# Gemmes som Windows-miljøvariabler for din bruger (ASC_WP_SITE_URL, ASC_WP_USER, ASC_WP_APP_PASSWORD).
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$site = Read-Host 'Hjemmeside (Enter = https://aktier.hangar18.dk)'
if (-not $site) { $site = 'https://aktier.hangar18.dk' }
$user = Read-Host 'WordPress-brugernavn'
$secure = Read-Host 'Application Password (vises ikke)' -AsSecureString
$plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
[Environment]::SetEnvironmentVariable('ASC_WP_SITE_URL', $site, 'User')
[Environment]::SetEnvironmentVariable('ASC_WP_USER', $user, 'User')
[Environment]::SetEnvironmentVariable('ASC_WP_APP_PASSWORD', $plain, 'User')
$env:ASC_WP_SITE_URL = $site; $env:ASC_WP_USER = $user; $env:ASC_WP_APP_PASSWORD = $plain
Write-Host 'Gemt. Tester forbindelsen...'
Set-Location -LiteralPath $root
& (Join-Path $root '.venv\Scripts\python.exe') -m stockscanner.site_sync --check-auth
Read-Host 'Tryk Enter for at lukke'
