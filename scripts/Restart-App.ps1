$ErrorActionPreference = 'Stop'
# Starter (eller genstarter) AI-Stock-Scanner i browseren på http://localhost:8501.
# Kaldes af Start-AI-Stock-Scanner.cmd i projektets rod. En kørende udgave af appen lukkes først, så den nye kode bruges.
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$port = 8501
try {
    if (-not (Test-Path -LiteralPath $python)) { throw "Mangler $python - opret venv'et først (se README)." }
    $old = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match '(?i)streamlit' -and
        $_.CommandLine -match '(?i)(?:^|[\s"\/])app\.py(?:[\s"]|$)' -and $_.CommandLine -like "*$root*"
    })
    if ($old.Count -gt 0) {
        Write-Host 'AI-Stock-Scanner kører allerede. Lukker den gamle udgave...'
        $old | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 1
    }
    Write-Host "Starter AI-Stock-Scanner på http://localhost:$port (luk dette vindue for at stoppe)."
    Set-Location -LiteralPath $root
    # Åbn browseren, når appen svarer (headless undgår Streamlits e-mail-spørgsmål ved første start)
    Start-Job -ArgumentList $port -ScriptBlock {
        param($port)
        foreach ($i in 1..60) {
            try {
                if ((Invoke-WebRequest "http://localhost:$port/_stcore/health" -UseBasicParsing -TimeoutSec 2).Content -eq 'ok') {
                    Start-Process "http://localhost:$port"; return
                }
            } catch {}
            Start-Sleep -Seconds 1
        }
    } | Out-Null
    & $python -m streamlit run (Join-Path $root 'app.py') --server.port $port --server.headless true --browser.gatherUsageStats false
    if ($LASTEXITCODE -ne 0) { throw "Appen stoppede med fejlkode $LASTEXITCODE." }
} catch {
    Write-Host "AI-Stock-Scanner kunne ikke starte: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host 'Tryk Enter for at lukke'
    exit 1
}
