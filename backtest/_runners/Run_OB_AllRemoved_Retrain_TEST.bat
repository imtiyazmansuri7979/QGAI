@echo off
setlocal
chcp 65001 >nul
title QGAI - OB/SR All Removed Retrain TEST

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_CTF_FADE=0"
set "QGAI_ABLATE="
set "TRAIN=C:\QGAI\engine\train.py"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "ARGS=--from 2026-04-01 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"
set "OUTDIR=C:\QGAI\backtest\results\ob_all_removed_RETRAIN_TEST"
set "MODELDIR=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\backups\OB_ALL_REMOVED_PRE_%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "BACKUP=%BACKUP: =0%"

cd /d "%ROOT%\engine"

echo ============================================================
echo   OB/SR ALL REMOVED - RETRAIN + 3-MONTH BACKTEST
echo ------------------------------------------------------------
echo   Current code removes all OB/SR model inputs:
echo     h4_resist_dist, h4_support_dist, h4_ob_strength
echo     h1_resist_dist, h1_support_dist, h1_ob_strength
echo.
echo   This test retrains the current 27-feature model, then replays:
echo     2026-04-01 to 2026-06-29
echo.
echo   Compare against old OB baseline:
echo     baseline = +31.8R
echo     D5      = +34.5R
echo     D6      = +34.7R
echo.
echo   WARNING: close live bridge before running this test.
echo   This script temporarily retrains data\models\final, then restores it.
echo ============================================================

if not exist "%MODELDIR%" (
    echo MODEL DIR NOT FOUND: %MODELDIR%
    pause
    exit /b 1
)

mkdir "%BACKUP%" >nul 2>nul
robocopy "%MODELDIR%" "%BACKUP%" /E >nul
if errorlevel 8 (
    echo BACKUP FAILED
    pause
    exit /b 1
)

echo.
echo [1/2] Retraining current 27-feature no-OB model...
"%PY%" "%TRAIN%"
if errorlevel 1 goto FAIL

echo.
echo [2/2] Running 3-month replay...
"%PY%" "%SCRIPT%" %ARGS% --out-dir "%OUTDIR%"
if errorlevel 1 goto FAIL

echo.
echo ============================================================
echo   TEST DONE - restoring original live model
echo ============================================================
robocopy "%BACKUP%" "%MODELDIR%" /MIR >nul
if errorlevel 8 (
    echo RESTORE FAILED - check backup: %BACKUP%
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   DONE
echo   Results:
echo     %OUTDIR%
echo.
echo   Open:
echo     %OUTDIR%\backtest_summary_st-htf.csv
echo     %OUTDIR%\backtest_report.txt
echo.
echo   If Total R is above +31.8R, no-OB beats old baseline.
echo   If Total R is above +34.7R, no-OB beats best D6 test.
echo ============================================================
pause
exit /b 0

:FAIL
echo.
echo ============================================================
echo   FAILED - restoring original live model
echo ============================================================
robocopy "%BACKUP%" "%MODELDIR%" /MIR >nul
if errorlevel 8 echo WARNING: RESTORE FAILED - check backup: %BACKUP%
pause
exit /b 1
