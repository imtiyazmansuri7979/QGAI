@echo off
setlocal
chcp 65001 >nul
title QGAI - FS67-01 - Priority Batch

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-01"
set "RESULT_ID=FS67-01_priority_batch"
set "QGAI_FEATURE_SWEEP_DIR=C:\QGAI\backtest\results\feature_sweep_67\%RESULT_ID%"
set "QGAI_FEATURE_SWEEP_RESULT_ID=%RESULT_ID%"

cd /d "%ROOT%\engine"

echo ============================================================
echo   %RUN_ID% - 67 FEATURE SWEEP - PRIORITY BATCH
echo ------------------------------------------------------------
echo   Result folder:
echo   %QGAI_FEATURE_SWEEP_DIR%
echo   Live model is NOT touched.
echo.
echo   Instructions:
echo   - Creates the 3-month baseline for FS67 screens.
echo   - Tests 10 priority features only.
echo   - 3-month result is screening only, not final proof.
echo   - If training lock appears, confirm no train.py is running before deleting it.
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
