@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%uninstall-ec4-liveprofessor-bridge.ps1"
if %errorlevel% neq 0 (
  echo.
  echo Une erreur est survenue pendant la suppression.
  pause
)
endlocal
