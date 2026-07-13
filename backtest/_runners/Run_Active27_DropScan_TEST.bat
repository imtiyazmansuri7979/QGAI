@echo off
setlocal EnableExtensions
chcp 65001 >nul
title QGAI - Active 27 Drop Scan LEAKAGE SAFE

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT=C:\QGAI\backtest\_scripts\active27_drop_scan.py"

rem ============================================================
rem STRICT OOS BOUNDARY
rem Training may use data only through 2026-03-31.
rem Backtest must begin on 2026-04-01 or later.
rem ============================================================
set "QGAI_TRAIN_CUTOFF=2026-03-31"
set "QGAI_STRICT_CUTOFF=1"
set "QGAI_EXPECTED_BACKTEST_START=2026-04-01"
set "QGAI_EXPECTED_BACKTEST_END=2026-06-29"

echo ============================================================
echo   ACTIVE 27 FEATURE DROP SCAN - LEAKAGE SAFE
echo ------------------------------------------------------------
echo   B00 = current 27-feature baseline
echo   D01-D27 = drop one active feature, retrain, 3-month backtest
echo.
echo   Training cutoff : %QGAI_TRAIN_CUTOFF%
echo   Backtest start  : %QGAI_EXPECTED_BACKTEST_START%
echo   Backtest end    : %QGAI_EXPECTED_BACKTEST_END%
echo.
echo   IMPORTANT:
echo   active27_drop_scan.py must preserve these environment values,
echo   train.py must enforce QGAI_TRAIN_CUTOFF,
echo   and the Python scan must verify model metadata before replay.
echo.
echo   WARNING: close live bridge before running.
echo   The script temporarily retrains data\models\final, then restores it.
echo ============================================================
echo.

if not exist "%PY%" (
    echo ERROR: Python not found:
    echo   %PY%
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo ERROR: Scan script not found:
    echo   %SCRIPT%
    pause
    exit /b 1
)

cd /d "%ROOT%" || (
    echo ERROR: Cannot open ROOT:
    echo   %ROOT%
    pause
    exit /b 1
)

"%PY%" -u "%SCRIPT%"
if errorlevel 1 (
    echo.
    echo ACTIVE-27 DROP SCAN FAILED OR LEAKAGE CHECK BLOCKED THE RUN
    pause
    exit /b 1
)

echo.
echo DONE. Results:
echo   C:\QGAI\backtest\results\active27_drop_SCAN_TEST
echo.
pause
exit /b 0
