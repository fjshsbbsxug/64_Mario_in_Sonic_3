@echo off
setlocal
title Mario 64 for Sonic 3 A.I.R. - mod builder
cd /d "%~dp0"

rem Find Python (the "py" launcher or "python" on PATH)
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Python 3 was not found.
    echo Please install it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during the installation.
    echo.
    pause
    exit /b 1
)

echo Installing / checking required Python packages...
%PY% -m pip install --quiet --disable-pip-version-check numpy pillow soundfile
echo.

rem A ROM can be dragged onto this file, otherwise the builder asks for it
if "%~1"=="" (
    %PY% build_mario_mod.py
) else (
    %PY% build_mario_mod.py "%~1"
    echo.
    pause
)
