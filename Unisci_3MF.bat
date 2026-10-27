@echo off
chcp 65001 >nul
title Unione Piatti 3MF - Bambu Studio

echo ===================================================
echo     Unione File 3MF Multi-Piatto per Bambu Studio
echo ===================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRORE] Python non e' installato o non si trova nel PATH di sistema.
    pause
    exit /b 1
)

python "%~dp0merge_3mf.py" %*

if "%~1"=="" (
    rem Se avviato con GUI, esce normalmente alla chiusura
) else (
    echo.
    echo Operazione completata.
    pause
)
