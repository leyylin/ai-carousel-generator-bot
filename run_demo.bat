@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title II Beauty Carousel - Interactive Demo
if not exist .venv\Scripts\python.exe (
  echo ERROR: Setup is not complete. Run setup_windows.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe ai_carousel_ollama.py
if errorlevel 1 echo ERROR: Generation failed. Check the messages above.
pause
