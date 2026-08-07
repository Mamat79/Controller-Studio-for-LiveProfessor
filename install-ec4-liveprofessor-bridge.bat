@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install-ec4-liveprofessor-bridge.ps1"
if %errorlevel% neq 0 (
  echo.
  echo Une erreur est survenue lors de l'installation.
  pause
)
endlocal
