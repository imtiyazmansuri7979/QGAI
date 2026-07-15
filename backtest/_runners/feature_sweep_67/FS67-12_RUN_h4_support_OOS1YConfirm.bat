@echo off
setlocal
chcp 65001 >nul
title QGAI - FS67-12 - h4_support_dist OOS1Y Confirm

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-12"
set "RESULT_ID=FS67-12_h4_support_oos1y_confirm"
set "QGAI_FEATURE_SWEEP_DIR=C:\QGAI\backtest\results\feature_sweep_67\%RESULT_ID%"
set "QGAI_FEATURE_SWEEP_RESULT_ID=%RESULT_ID%"

REM Same window/cutoff as OOS1Y-01 so this candidate compares apples-to-apples.
set "QGAI_SWEEP_TRAIN_CUTOFF=2025-06-28"
set "QGAI_SWEEP_FROM=2025-06-29"
set "QGAI_SWEEP_TO=2026-06-29"

cd /d "%ROOT%\engine"

echo ============================================================
echo   %RUN_ID% - h4_support_dist - OOS1Y CONFIRM
echo ------------------------------------------------------------
echo   Tests only the FS67-01 winner candidate:
echo     h4_support_dist
echo.
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
echo.
echo   Instructions:
echo   - Tests only h4_support_dist against the OOS1Y window.
echo   - Baseline may be rerun inside this isolated confirmation folder.
echo   - Use result as OOS confirmation only, not live adoption by itself.
echo   - If it hurts OOS1Y, keep the feature dropped.
echo ============================================================

"%PY%" run_feature_sweep.py --tier priority_batch --only h4_support_dist
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto fail

echo.
echo ============================================================
echo   DONE %RUN_ID%
echo   Summary: %QGAI_FEATURE_SWEEP_DIR%\%RESULT_ID%_SUMMARY.csv
echo ============================================================
pause
exit /b 0

:fail
echo.
echo ============================================================
echo   FAILED %RUN_ID%
echo   Check logs in:
echo   %QGAI_FEATURE_SWEEP_DIR%
echo ============================================================
pause
exit /b %RC%
