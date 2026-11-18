@echo off
setlocal
cd /d "%~dp0"
title FM Explorer (watching)
set PY=
where py >nul 2>nul && set PY=py
if "%PY%"=="" ( where python >nul 2>nul && set PY=python )
if "%PY%"=="" (
  echo Python is not installed.
  echo Install it from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^), then run this again.
  pause
  exit /b 1
)
echo Checking for fmsave updates ^(new FM patches often need a newer fmsave^)...
%PY% -m pip install --upgrade --quiet --disable-pip-version-check fmsave
if errorlevel 1 (
  %PY% -c "import fmsave" >nul 2>nul
  if errorlevel 1 (
    echo Could not install fmsave. Check your internet connection and try again.
    pause
    exit /b 1
  )
  echo Could not check for updates, using the installed fmsave.
)
echo.
echo Watching your FM saves. Every time FM saves, the explorer rebuilds itself (1-2 minutes)
echo and the open page reloads on its own. Leave this window open while you play.
echo Close this window to stop.
%PY% fm_explorer.py --watch %*
if errorlevel 1 pause
