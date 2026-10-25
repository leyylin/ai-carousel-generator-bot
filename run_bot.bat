@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
title UUSE Beauty Carousel Bot

if not exist .venv\Scripts\python.exe (
  echo ERROR: .venv not found. Run setup_windows.bat first.
  pause
  exit /b 1
)

.venv\Scripts\python.exe main.py
if errorlevel 1 (
  echo.
  echo Bot stopped with an error. See the log above.
  pause
)
