@echo off
rem Ugentlig mandagsliste for research-aktierne (startes af Windows Opgavestyring hver mandag kl. 8).
cd /d "%~dp0.."
echo ==== %date% %time% ====>> data\mandagsliste.log
.venv\Scripts\python.exe -W ignore scan_cli.py --mandagsliste >> data\mandagsliste.log 2>&1
