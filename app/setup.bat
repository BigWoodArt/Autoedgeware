@echo off

reg Query "HKLM\Hardware\Description\System\CentralProcessor\0" | find /i "x86" > NUL && set OS=32BIT || set OS=64BIT

:: cd to script's directory in case Windows sets the working directory to something else
cd /D "%~dp0"

echo +==============[ Autoedgeware Setup~ ]==============+
echo Python version:
py --version
echo:
echo NOTE: Python versions older than 3.12 might have compatibility issues.
echo:

if not %errorlevel%==0 (
  echo Could not find Python.
  echo Downloading installer from python.org, please wait...

  if %OS%==32BIT powershell -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.12.6/python-3.12.6.exe -OutFile pyinstaller.exe"
  if %OS%==64BIT powershell -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.12.6/python-3.12.6-amd64.exe -OutFile pyinstaller.exe"

  echo Done downloading executable.
  echo Please complete installation through the installer before continuing, make sure "Add Python to PATH" is checked.
  start "Python Installer" "%CD%\pyinstaller.exe"
  pause

  py --version
  if not %errorlevel%==0 (
    echo Python still could not be found.
    pause
    exit /b 1
  )
)

echo pip version:
py -m pip --version
if not %errorlevel%==0 (
  echo Could not find pip.
  echo Installing pip with ensurepip...
  py -m ensurepip --upgrade

  py -m pip --version
  if not %errorlevel%==0 (
    echo pip still could not be found.
    pause
    exit /b 1
  )
)

echo Installing requirements (this covers real Edgeware's own dependencies too - video/audio playback, tray icon, etc)...
py -m pip install -r requirements.txt
if not %errorlevel%==0 (
  echo Failed to install requirements.
  pause
  exit /b 1
)

if not exist edgeware_core\data mkdir edgeware_core\data

if not exist edgeware_core\data\libmpv-2.dll (
  echo Installing libmpv - needed for video/audio popup playback...
  if not exist edgeware_core\data\7z.exe powershell -Command "Invoke-WebRequest https://7-zip.org/a/7zr.exe -OutFile edgeware_core\data\7z.exe"
  if not exist edgeware_core\data\mpv.7z (
    if %OS%==32BIT powershell -Command "Invoke-WebRequest https://sourceforge.net/projects/mpv-player-windows/files/libmpv/mpv-dev-i686-20250420-git-3600c71.7z/download -UserAgent 'Wget' -OutFile edgeware_core\data\mpv.7z"
    if %OS%==64BIT powershell -Command "Invoke-WebRequest https://sourceforge.net/projects/mpv-player-windows/files/libmpv/mpv-dev-x86_64-20250420-git-3600c71.7z/download -UserAgent 'Wget' -OutFile edgeware_core\data\mpv.7z"
  )
  edgeware_core\data\7z.exe e edgeware_core\data\mpv.7z -oedgeware_core\data libmpv-2.dll

  if not exist edgeware_core\data\libmpv-2.dll (
    echo Failed to install libmpv. Video/audio popups won't work until this is resolved - see edgeware_core\requirements.txt.
    pause
    exit /b 1
  )
)

where ffprobe >nul 2>&1
if not %errorlevel%==0 (
  echo ffprobe/ffmpeg was not found - video popups need it.
  where winget >nul 2>&1
  if %errorlevel%==0 (
    echo Installing ffmpeg with winget...
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    echo If videos do not play, close this window and run again so Windows picks up ffmpeg.
  ) else (
    echo Please install ffmpeg from https://ffmpeg.org/download.html and add it to PATH.
  )
)

:: Remember that setup finished for this version, so run.bat can skip it next time.
copy /Y VERSION .setup_ok >nul

echo:
echo Setup complete.
