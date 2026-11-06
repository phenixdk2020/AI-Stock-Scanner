@echo off
rem Entry-tjek mellem mandagslisterne (Windows Opgavestyring, indhenter naar PC-en taendes). Bruger ikke GPU.
cd /d "%~dp0.."
echo ==== %date% %time% entry-tjek ====>> data\mandagsliste.log
.venv\Scripts\python.exe -W ignore scan_cli.py --entry-tjek >> data\mandagsliste.log 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\notify.ps1 >> data\mandagsliste.log 2>&1
