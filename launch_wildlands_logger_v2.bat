@echo off
setlocal
title Ghost Recon Wildlands - Startup Logger v2
cd /d "%~dp0"

if not exist "%~dp0wildlands_startup_logger_v2.py" (
    echo.
    echo [ERREUR] wildlands_startup_logger_v2.py est introuvable.
    echo.
    pause
    exit /b 1
)

py -3 "%~dp0wildlands_startup_logger_v2.py"
set "RC=%ERRORLEVEL%"

echo.
echo Logger termine avec le code %RC%.
echo.
pause
