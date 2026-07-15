@echo off
setlocal
chcp 65001 >nul
title QGAI - FS67-04 - Tier3 Remaining

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-04"
set "RESULT_ID=FS67-04_tier3_remaining"
set "QGAI_FEATURE_SWEEP_DIR=C:\QGAI\backtest\results\feature_sweep_67\%RESULT_ID%"
set "QGAI_FEATURE_SWEEP_RESULT_ID=%RESULT_ID%"
set "QGAI_SWEEP_BASELINE_JSON=C:\QGAI\backtest\results\feature_sweep_67\FS67-01_priority_batch\baseline\result.json"

cd /d "%ROOT%\engine"

echo ============================================================
echo   %RUN_ID% - 67 FEATURE SWEEP - TIER 3 REMAINING
echo ------------------------------------------------------------
echo   Result folder:
echo   %QGAI_FEATURE_SWEEP_DIR%
echo   Reuse baseline:
echo   %QGAI_SWEEP_BASELINE_JSON%
echo   Live model is NOT touched.
echo.
echo   Instructions:
echo   - Does NOT rerun baseline.
echo   - Uses FS67-01 baseline result.json.
echo   - Tests remaining dropped features one at a time.
echo   - This is a screening run only.
echo ============================================================

"%PY%" run_feature_sweep.py --tier remaining
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
