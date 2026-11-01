<#
.SYNOPSIS
  Starter lokal AI-Stock-Scanner på Windows.
.EXAMPLE
  .\scripts\Start-Scanner.ps1 -Setup
  .\scripts\Start-Scanner.ps1 -Check -Live -Ollama
  .\scripts\Start-Scanner.ps1
#>
[CmdletBinding()]
param(
    [switch]$Setup,
    [switch]$Check,
    [switch]$Live,
    [switch]$Ollama
)
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
Push-Location $root
try {
    if ($Setup) {
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if (-not $launcher) {
            throw 'Python-launcheren py.exe mangler. Installer Python 3.11 eller nyere.'
        }
        if (-not (Test-Path -LiteralPath $python)) {
            & py -3 -m venv .venv
            if ($LASTEXITCODE -ne 0) { throw 'Kunne ikke oprette Python-venv.' }
        }
        & $python -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Kunne ikke installere Python-afhængigheder.' }
        Write-Host 'Setup færdigt. Kør nu: .\scripts\Start-Scanner.ps1 -Check -Live -Ollama'
        return
    }
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Ingen .venv fundet. Kør først: .\scripts\Start-Scanner.ps1 -Setup'
    }
    if ($Check) {
        $argsList = @('-m', 'stockscanner.doctor')
        if ($Live) { $argsList += '--live' }
        if ($Ollama) { $argsList += '--ollama' }
        & $python @argsList
    } else {
        & $python -m streamlit run app.py
    }
    if ($LASTEXITCODE -ne 0) { throw "Programmet sluttede med fejlkode $LASTEXITCODE" }
}
finally {
    Pop-Location
}
