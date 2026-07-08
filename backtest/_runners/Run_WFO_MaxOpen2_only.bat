@echo off
setlocal
chcp 65001 >nul
title QGAI - WFO max_open=2 ONLY (baseline already known +444.7R)

REM =====================================================================
REM  max_open=2 WFO ONLY — baseline max_open=1 is already validated at
REM  +444.7R (PART-1, reproduces stably), so no need to re-run it.
REM  Compare this result directly to +444.7R.
REM
REM  Fixed-lot R-frame (same as +444.7R baseline). 1.5%-per-trade risk
REM  scaling is the LIVE sizing decision (3% total), separate from this
REM  OOS R-edge measurement.
REM
REM  ⚠️ Needs train.py stack on this PC. Backtest-side only. ~1.5 hr.
REM  GATE: WFO total R materially > +444.7R AND per-week stable.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

cd /d "%ROOT%\engine"

echo ============================================================
echo WFO max_open=2  %DATE% %TIME%   (baseline = +444.7R known)
echo ============================================================
"%PY%" run_wfo.py --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --max-open 2 --results-dir wfo_maxopen2_test
if errorlevel 1 goto fail

echo.
echo ============================================================
echo DONE %DATE% %TIME%
echo   result : backtest\results\wfo_maxopen2_test\_WFO_SUMMARY.txt
echo   COMPARE its Total R vs +444.7R baseline.
echo   In-sample was +758R (2x) — if OOS holds, +50%% goal reached.
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED — resume-safe, re-run. ***
pause
exit /b 1
