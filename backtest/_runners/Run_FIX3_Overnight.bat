@echo off
setlocal
chcp 65001 >nul
title QGAI - FIX-3 Overnight (reversal-close overlap + R impact)

REM =====================================================================
REM  FIX-3 (Fable-5 #1) — measure whether modeling live reversal-close in
REM  the backtest improves the live-vs-backtest overlap (currently ~12%).
REM
REM  Runs 5 steps, results all under backtest\results\fix3_2026-07-08\ :
REM   1. Refresh shadow ledger (live-computed trades from signals_all.csv)
REM   2. Backtest LIVE-period (2026-06-09→07-07) reversal OFF  -> overlap_off
REM   3. Backtest LIVE-period reversal ON (QGAI_BT_REVERSAL=1) -> overlap_on
REM   4. reconcile_shadow for BOTH -> entry-overlap %% each
REM   5. Full-year backtest reversal ON -> R impact vs +444.7R baseline
REM
REM  ⚠️ Backtest-side only — live trading NOT touched. Uses the validated
REM     raw-36 model already in data\models\final.
REM  Total ~1.5-2 hr. Resume-safe (skips a step whose report.txt exists).
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT=C:\QGAI\backtest\results\fix3_2026-07-08"

set "COMMON=--equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"

if not exist "%OUT%" mkdir "%OUT%"
cd /d "%ROOT%\engine"

echo ============================================================
echo FIX-3 OVERNIGHT  %DATE% %TIME%
echo ============================================================

echo [1/5] Refresh shadow ledger (live-computed)...
"%PY%" shadow_ledger.py

REM ---- 2. LIVE-period backtest, reversal OFF ----
set QGAI_BT_REVERSAL=
set "O1=%OUT%\liveperiod_reversal_OFF"
echo [2/5] Backtest live-period 2026-06-09..07-07  reversal OFF...
if exist "%O1%\backtest_report.txt" ( echo skip ) else (
  "%PY%" "%SCRIPT%" --from 2026-06-09 --to 2026-07-07 %COMMON% --out-dir "%O1%"
  if errorlevel 1 goto fail
)

REM ---- 3. LIVE-period backtest, reversal ON ----
set QGAI_BT_REVERSAL=1
set "O2=%OUT%\liveperiod_reversal_ON"
echo [3/5] Backtest live-period  reversal ON (QGAI_BT_REVERSAL=1)...
if exist "%O2%\backtest_report.txt" ( echo skip ) else (
  "%PY%" "%SCRIPT%" --from 2026-06-09 --to 2026-07-07 %COMMON% --out-dir "%O2%"
  if errorlevel 1 goto fail
)

REM ---- 4. reconcile both vs shadow (overlap %) ----
echo [4/5] Reconcile overlap (backtest vs live shadow)...
"%PY%" reconcile_shadow.py --from 2026-06-09 --to 2026-07-07 --backtest-glob "%O1%\backtest_trades_*.csv" --out-dir "%OUT%\reconcile_OFF"
"%PY%" reconcile_shadow.py --from 2026-06-09 --to 2026-07-07 --backtest-glob "%O2%\backtest_trades_*.csv" --out-dir "%OUT%\reconcile_ON"

REM ---- 5. full-year reversal ON (R impact vs +444.7R) ----
set QGAI_BT_REVERSAL=1
set "O3=%OUT%\fullyear_reversal_ON"
echo [5/5] Full-year backtest reversal ON (R impact)...
if exist "%O3%\backtest_report.txt" ( echo skip ) else (
  "%PY%" "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 %COMMON% --out-dir "%O3%"
  if errorlevel 1 goto fail
)

echo.
echo ============================================================
echo FIX-3 OVERNIGHT DONE  %DATE% %TIME%
echo Root: %OUT%
echo READ:
echo   reconcile_OFF\*summary*  = overlap %% WITHOUT reversal (baseline ~12%%)
echo   reconcile_ON\*summary*   = overlap %% WITH reversal   (target higher)
echo   fullyear_reversal_ON\backtest_report.txt = R vs +444.7R baseline
echo ============================================================
pause
exit /b 0

:fail
echo *** FIX-3 run FAILED %DATE% %TIME% — resume-safe, re-run. ***
pause
exit /b 1
