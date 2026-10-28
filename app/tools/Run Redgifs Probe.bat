@echo off
cd /D "%~dp0"
echo Asking Redgifs about niches. This takes about a minute...
py -3 probe_redgifs_niches.py
echo.
echo Done. Send me the file "probe_redgifs.txt" from this folder.
start "" explorer /select,"%~dp0probe_redgifs.txt"
pause
