@echo off
setlocal
chcp 65001 >nul
title QGAI - FS67-09 - Feature Sweep Sanity Active2

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-09"
set "RESULT_ID=FS67-09_sanity_active2"
set "QGAI_FEATURE_SWEEP_DIR=C:\QGAI\backtest\results\feature_sweep_67\%RESULT_ID%"
set "QGAI_FEATURE_SWEEP_RESULT_ID=%RESULT_ID%"

cd /d "%ROOT%\engine"

echo ============================================================
echo   %RUN_ID% - FEATURE SWEEP SANITY TEST
echo ------------------------------------------------------------
echo   Runs active tier with --limit 2 only.
echo   Result folder:
echo   %QGAI_FEATURE_SWEEP_DIR%
echo   Live model is NOT touched.
echo ============================================================

"%PY%" run_feature_sweep.py --tier active --limit 2
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto fail

echo.
echo ============================================================
echo   DONE %RUN_ID%
echo   Summary: %QGAI_FEATURE_SWEEP_DIR%\%RESULT_ID%_SUMMARY.csv
echo   If this looks right, run:
echo   feature_sweep_67\FS67-01_RUN_PriorityBatch.bat
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
