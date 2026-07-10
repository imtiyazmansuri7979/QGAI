@echo off
setlocal
chcp 65001 >nul
title QGAI - ADX-Death WFO TEST NO-VOLUME (2 weeks only)

REM =====================================================================
REM  QUICK TEST - 2 weeks only, error check before full overnight run.
REM  Current retrained model must be NO-VOLUME:
REM    tick_volume / volume are NOT model inputs.
REM  Tests K3 N4 X1.0 (best cell) to verify env vars work in WFO.
REM  About 15 min. If OK, run Run_ADXDeath_WFO_Validate.bat for full run.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

cd /d "%ROOT%\engine"
echo ============================================================
echo ADX-DEATH WFO TEST NO-VOLUME (2 weeks)  %DATE% %TIME%
echo   K3 N4 X1.0 - error check only
echo   Fresh result folder: wfo_adxdeath_novol_test_20260710
echo ============================================================

"%PY%" test_tickvol_feature.py
if errorlevel 1 goto fail

set "QGAI_ADX_DEATH=1"
set "QGAI_ADX_DEATH_K=3"
set "QGAI_ADX_DEATH_N=4"
set "QGAI_ADX_DEATH_MIN_R=1.0"

"%PY%" run_wfo.py --start 2025-06-23 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --weeks 2 --results-dir wfo_adxdeath_novol_test_20260710
if errorlevel 1 goto fail

set "QGAI_ADX_DEATH="
echo.
echo ============================================================
echo TEST DONE. Check output above for errors.
echo   If OK then run Run_ADXDeath_WFO_Validate.bat (full overnight)
echo ============================================================
pause
exit /b 0

:fail
echo.
echo *** FAILED %DATE% %TIME% - fix error above, then run again. ***
pause
exit /b 1
