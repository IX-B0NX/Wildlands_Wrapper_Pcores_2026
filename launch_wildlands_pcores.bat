@echo off
setlocal
title Ghost Recon Wildlands - P-Core Wrapper

set "WRAPPER=%~dp0wildlands_pcore_wrapper_v1_2.py"
set "GAME=D:\SteamLibrary\steamapps\common\Wildlands\GRW.exe"

echo.
echo ==========================================
echo   Ghost Recon Wildlands - P-Core Wrapper
echo ==========================================
echo.
echo Wrapper : "%WRAPPER%"
echo Jeu     : "%GAME%"
echo.

if not exist "%WRAPPER%" (
    echo [ERREUR] Le fichier Python est introuvable.
    echo Place wildlands_pcore_wrapper_v1_2.py dans le meme dossier que ce BAT.
    echo.
    pause
    exit /b 1
)

if not exist "%GAME%" (
    echo [ERREUR] GRW.exe est introuvable ici :
    echo "%GAME%"
    echo.
    echo Verifie le chemin d'installation de Wildlands.
    echo.
    pause
    exit /b 2
)

py -3 "%WRAPPER%" "%GAME%"
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
    echo [ERREUR] Le wrapper s'est termine avec le code %RC%.
) else (
    echo [OK] GRW.exe a ete lance sur les P-cores.
)
echo.
pause
exit /b %RC%
