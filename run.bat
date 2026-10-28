@echo off
cd /D "%~dp0"

:: START HERE: double-click this file. Everything else lives in the "app" folder.
:: First launch (and after each update) it sets things up; after that it opens straight away.

:: Updating from an older version that kept everything in this folder? Move it into "app" first.
set "OLD=0"
if exist "gui_main.py" set "OLD=1"
if "%OLD%"=="1" call :migrate_old_layout
if errorlevel 1 exit /b 1

:: Media now lives next to this file. Bring over a media folder from the app folder.
if exist "app\media\" call :move_media
if errorlevel 1 exit /b 1

cd /D "%~dp0app"
set "DONE="
set "CUR="
if exist .setup_ok set /p DONE=<.setup_ok
set /p CUR=<VERSION
set "QUICK=0"
if defined DONE if "%DONE%"=="%CUR%" set "QUICK=1"
if "%QUICK%"=="1" (
  py --version >nul 2>&1
  if not errorlevel 1 goto launch
)

call setup.bat
if not %errorlevel%==0 (
  echo Setup failed - see above.
  pause
  exit /b 1
)

:launch
echo Starting Autoedgeware...
start "" pyw gui_main.py
exit /b 0


:migrate_old_layout
echo Updating the folder layout. Your downloads, presets and settings are kept.
echo (This can take a minute when there are many files. Please wait.)
if not exist "app\ae_settings" mkdir "app\ae_settings"
if not exist "app\edgeware_core\data" mkdir "app\edgeware_core\data"
call :mv "logs" "app\logs"
for %%F in (ae_settings\*.json ae_settings\original_wallpaper.*) do move /Y "%%F" "app\ae_settings\" >nul
for %%F in (edgeware_core\data\*.dll) do move /Y "%%F" "app\edgeware_core\data\" >nul
if not exist "old_version_backup" mkdir "old_version_backup"
for %%D in (core gui sources tests tools edgeware_core ae_settings __pycache__) do call :mv "%%D" "old_version_backup\%%D"
for %%F in (*.py requirements.txt setup.bat VERSION .setup_ok pyinstaller.exe) do if exist "%%F" move /Y "%%F" "old_version_backup\" >nul
echo Done. The old program files are in "old_version_backup" - you can delete that folder when everything works.
exit /b 0

:move_media
echo Moving your media folder next to run.bat. Please wait.
if not exist "media" mkdir "media"
call :mv "app\media" "media"
if exist "app\media\" (
  echo.
  echo Some files could not be moved yet - they may be busy, for example OneDrive syncing.
  echo Close other programs, wait a minute, and run this again.
  pause
  exit /b 1
)
echo Done. Your media is now in the "media" folder.
exit /b 0

:: Moves a whole folder and merges it into the destination if that already exists.
:: robocopy removes each file from the source only after it has been copied.
:mv
if exist "%~1\" robocopy "%~1" "%~2" /E /MOVE /R:3 /W:2 /NFL /NDL /NJH /NJS /NP >nul
exit /b 0
