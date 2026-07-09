@echo off
title QGAI - Backup LIVE Models (run BEFORE any retrain)
REM ============================================================
REM  Backs up the LIVE model folders BEFORE 3_Train_Models.bat
REM  overwrites them. If a retrain fails the WFO-gate, restore
REM  from the timestamped copy this makes.
REM    Source : C:\QGAI\data\models\final     (live .pkl the bot serves)
REM             C:\QGAI\data\models\registry
REM    Dest   : C:\QGAI\data\models\backups\models_YYYYMMDD_HHMMSS\
REM  Read-only on the source (robocopy copy, not move). Safe to re-run.
REM ============================================================
setlocal
set "SRC=C:\QGAI\data\models"
set "BKROOT=C:\QGAI\data\models\backups"

REM -- timestamp via PowerShell (locale-proof: yyyyMMdd_HHmmss) --
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%T"
set "DEST=%BKROOT%\models_%TS%"

echo ============================================================
echo   QGAI - MODEL BACKUP (before retrain)
echo   From : %SRC%\final  +  %SRC%\registry
echo   To   : %DEST%
echo ============================================================
echo.

if not exist "%SRC%\final" (
    echo  ^!^! LIVE model folder not found: %SRC%\final
    echo     Nothing to back up - is the path correct?
    pause >nul
    exit /b 1
)

mkdir "%DEST%" 2>nul

echo [1/2] Backing up final\ ...
robocopy "%SRC%\final"    "%DEST%\final"    /E /R:2 /W:2 /NFL /NDL /NP
echo.
echo [2/2] Backing up registry\ ...
robocopy "%SRC%\registry" "%DEST%\registry" /E /R:2 /W:2 /NFL /NDL /NP

echo.
REM robocopy exit codes 0-7 = success (8+ = error)
if errorlevel 8 (
    echo  ^!^! BACKUP HAD ERRORS ^(robocopy code %errorlevel%^) - check above. Do NOT retrain yet.
) else (
    echo  ^>^> Backup OK. Saved to:
    echo     %DEST%
    echo     To restore later: copy final\ + registry\ from that folder back into %SRC%\
)
echo.
echo ============================================================
echo   Press any key to close.
echo ============================================================
pause >nul
endlocal
