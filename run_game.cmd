@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please follow the Windows setup steps in README.md first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" game.py
if errorlevel 1 pause
endlocal
