@echo off
rem Ugentlig mandagsliste for research-aktierne (startes af Windows Opgavestyring hver mandag kl. 8).
rem Opdaterer først sammenligningsuniverset, hvis det er over 7 dage gammelt.
cd /d "%~dp0.."
echo ==== %date% %time% ====>> data\mandagsliste.log
.venv\Scripts\python.exe -W ignore scripts\build_universe.py >> data\mandagsliste.log 2>nul
.venv\Scripts\python.exe -W ignore scan_cli.py --mandagsliste >> data\mandagsliste.log 2>&1
