@echo off
setlocal
cd /d "%~dp0"
title AI Carousel Generator - Setup

echo ==============================================
echo AI Carousel Generator v2 - Setup
echo ==============================================
echo.

REM Prefer Python 3.12 or 3.11. ASCII-only batch file avoids Windows CMD encoding issues.
set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 --version >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3.12"
  if not defined PYTHON_CMD (
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3.11"
  )
)
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo ERROR: Python was not found.
  echo Install Python 3.11 or 3.12 from https://www.python.org/downloads/windows/
  echo During installation, enable Add Python to PATH.
  pause
  exit /b 1
)

echo Using Python command: %PYTHON_CMD%
%PYTHON_CMD% --version
if errorlevel 1 goto error

if not exist .venv\Scripts\python.exe (
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto error
)

.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto error

if not exist .env copy /Y .env.example .env >nul

echo.
echo Setup completed successfully.
echo Next: open .env and set BOT_TOKEN from @BotFather
echo Then launch run_bot.bat
pause
exit /b 0

:error
echo.
echo ERROR: Setup failed. Copy the error text above and send it for troubleshooting.
pause
exit /b 1
