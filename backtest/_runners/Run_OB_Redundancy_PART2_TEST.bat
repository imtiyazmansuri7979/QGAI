@echo off
setlocal
chcp 65001 >nul
title QGAI - OB Redundancy PART 2 Retrain TEST

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_CTF_FADE=0"
set "TRAIN=C:\QGAI\engine\train.py"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "ARGS=--from 2026-04-01 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"
set "OUTBASE=C:\QGAI\backtest\results\ob_redundancy_RETRAIN_TEST"
set "MODELDIR=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\backups\OB_REDUNDANCY_PART2_PRE_%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "BACKUP=%BACKUP: =0%"

cd /d "%ROOT%\engine"

echo ============================================================
echo   OB REDUNDANCY PART 2 - RETRAIN TEST
echo   Runs: D4 + D5 + D6
echo   NOTE: compare against baseline from PART 1 or full AB runner.
echo   Results: %OUTBASE%
echo ============================================================

mkdir "%BACKUP%" >nul 2>nul
robocopy "%MODELDIR%" "%BACKUP%" /E >nul
if errorlevel 8 ( echo BACKUP FAILED & pause & exit /b 1 )

call :RUN_ONE D4_drop_h1_ob_strength "h1_ob_strength"
if errorlevel 1 goto FAIL
call :RUN_ONE D5_drop_h4resist_h4ob "h4_resist_dist,h4_ob_strength"
if errorlevel 1 goto FAIL
call :RUN_ONE D6_drop_h1support_h1ob "h1_support_dist,h1_ob_strength"
if errorlevel 1 goto FAIL
goto RESTORE_OK

:RUN_ONE
set "NAME=%~1"
set "DROP=%~2"
echo.
echo [%NAME%] dropping %DROP%
set "QGAI_ABLATE=%DROP%"
"%PY%" "%TRAIN%"
if errorlevel 1 exit /b 1
"%PY%" "%SCRIPT%" %ARGS% --out-dir "%OUTBASE%\%NAME%"
if errorlevel 1 exit /b 1
exit /b 0

:FAIL
echo FAILED - restoring original live model
set "QGAI_ABLATE="
robocopy "%BACKUP%" "%MODELDIR%" /MIR >nul
pause
exit /b 1

:RESTORE_OK
set "QGAI_ABLATE="
robocopy "%BACKUP%" "%MODELDIR%" /MIR >nul
if errorlevel 8 ( echo RESTORE FAILED & pause & exit /b 1 )
echo.
echo PART 2 DONE. Original live model restored.
echo Results in: %OUTBASE%
pause
exit /b 0
