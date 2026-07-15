@echo off
setlocal
chcp 65001 >nul
title QGAI - FS67-11 - Priority Batch OOS1Y Confirm

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-11"
set "RESULT_ID=FS67-11_priority_batch_oos1y_confirm"
set "QGAI_FEATURE_SWEEP_DIR=C:\QGAI\backtest\results\feature_sweep_67\%RESULT_ID%"
set "QGAI_FEATURE_SWEEP_RESULT_ID=%RESULT_ID%"

REM Same window/cutoff as OOS1Y-01 so feature results compare apples-to-apples.
set "QGAI_SWEEP_TRAIN_CUTOFF=2025-06-28"
set "QGAI_SWEEP_FROM=2025-06-29"
set "QGAI_SWEEP_TO=2026-06-29"

cd /d "%ROOT%\engine"

echo ============================================================
echo   %RUN_ID% - PRIORITY BATCH - OOS1Y CONFIRM
echo ------------------------------------------------------------
echo   Baseline match:
echo     OOS1Y-01 current-config clean OOS 1yr
echo.
echo   Train cutoff : %QGAI_SWEEP_TRAIN_CUTOFF%
echo   Backtest     : %QGAI_SWEEP_FROM% to %QGAI_SWEEP_TO%
echo.
echo   Result folder:
echo   %QGAI_FEATURE_SWEEP_DIR%
echo.
echo   Live model is NOT touched.
echo ============================================================

"%PY%" run_feature_sweep.py --tier priority_batch
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto fail

echo.
echo ============================================================
echo   DONE %RUN_ID%
echo   Summary: %QGAI_FEATURE_SWEEP_DIR%\%RESULT_ID%_SUMMARY.csv
echo ============================================================
pause
exit /b %RC%

:fail
echo.
echo ============================================================
echo   FAILED %RUN_ID%
echo   Check logs in:
echo   %QGAI_FEATURE_SWEEP_DIR%
echo ============================================================
pause
exit /b %RC%
