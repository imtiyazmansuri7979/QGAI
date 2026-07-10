@echo off
setlocal
chcp 65001 >nul
title QGAI - ADX-Death WFO Validation NO-VOLUME (top-2 + baseline)

REM =====================================================================
REM  WFO out-of-sample validation for ADX-Death top-2 cells.
REM  Current retrained model must be NO-VOLUME:
REM    tick_volume / volume are NOT model inputs.
REM
REM    1. Baseline (OFF)
REM    2. K3 N4 X1.0  (+409.1R in-sample, best)
REM    3. K3 N4 X0.3  (+404.7R in-sample, 2nd)
REM
REM  True OOS: weekly retrain, trade next week unseen.
REM  Resume-safe: re-run to continue where it stopped.
REM  GATE: >= +444.7R baseline to adopt.
REM  About 2 hr each = about 6 hr total. Leave running overnight.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "WFO_ARGS=--start 2025-06-23 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01"

cd /d "%ROOT%\engine"
echo ============================================================
echo ADX-DEATH WFO VALIDATION NO-VOLUME  %DATE% %TIME%
echo   3 runs: baseline + K3N4X1.0 + K3N4X0.3
echo   GATE: >= +444.7R to adopt
echo   Fresh result folders use prefix: wfo_adxdeath_novol_*_20260710
echo ============================================================

"%PY%" test_tickvol_feature.py
if errorlevel 1 goto fail

REM --- 1. BASELINE (ADX_DEATH OFF) ---
set "QGAI_ADX_DEATH="
set "QGAI_ADX_DEATH_K="
set "QGAI_ADX_DEATH_N="
set "QGAI_ADX_DEATH_MIN_R="
echo.
echo [1/3] BASELINE (ADX_DEATH OFF) ...
"%PY%" run_wfo.py %WFO_ARGS% --results-dir wfo_adxdeath_novol_baseline_20260710
if errorlevel 1 goto fail

REM --- 2. K3 N4 X1.0 (best in-sample) ---
set "QGAI_ADX_DEATH=1"
set "QGAI_ADX_DEATH_K=3"
set "QGAI_ADX_DEATH_N=4"
set "QGAI_ADX_DEATH_MIN_R=1.0"
echo.
echo [2/3] K3 N4 X1.0 ...
"%PY%" run_wfo.py %WFO_ARGS% --results-dir wfo_adxdeath_novol_K3N4X1p0_20260710
if errorlevel 1 goto fail

REM --- 3. K3 N4 X0.3 (2nd best) ---
set "QGAI_ADX_DEATH=1"
set "QGAI_ADX_DEATH_K=3"
set "QGAI_ADX_DEATH_N=4"
set "QGAI_ADX_DEATH_MIN_R=0.3"
echo.
echo [3/3] K3 N4 X0.3 ...
"%PY%" run_wfo.py %WFO_ARGS% --results-dir wfo_adxdeath_novol_K3N4X0p3_20260710
if errorlevel 1 goto fail

REM --- Clean up env ---
set "QGAI_ADX_DEATH="
set "QGAI_ADX_DEATH_K="
set "QGAI_ADX_DEATH_N="
set "QGAI_ADX_DEATH_MIN_R="

echo.
echo ============================================================
echo ALL 3 WFO RUNS DONE  %DATE% %TIME%
echo   Results:
echo     backtest\results\wfo_adxdeath_novol_baseline_20260710\
echo     backtest\results\wfo_adxdeath_novol_K3N4X1p0_20260710\
echo     backtest\results\wfo_adxdeath_novol_K3N4X0p3_20260710\
echo   Compare Total R - GATE >= +444.7R to adopt.
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED %DATE% %TIME% - resume-safe: re-run to continue. ***
pause
exit /b 1
