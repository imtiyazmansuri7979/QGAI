@echo off
setlocal
chcp 65001 >nul
title QGAI - Shadow-Skips Missed-Profit Diagnostic (FULL, 12 weeks)

REM =====================================================================
REM  FULL confirm of Run_ShadowSkips_MissedProfit_TEST.bat - only run this
REM  AFTER the TEST bat finished clean (no crashes, files appeared).
REM
REM  Same 12-week window as volhtfgate_wfo_TEST_A_off (2026-04-06 ->
REM  2026-06-29, +32.5R / 207 real trades honest baseline) so all 3 shadow
REM  runs below are directly comparable to that real result and to each
REM  other.
REM
REM  Runs 3 sequential counterfactual passes (see backtest_replay.py's
REM  QGAI_SHADOW_SKIPS override for exact mechanics):
REM    [1] strong = aligned_strong bucket only (4/4 HTF signals agree) --
REM        this is the EXACT bucket Imtiyaz flagged: "most aligned_strong
REM        bars are skipped, not traded"
REM    [2] weak   = aligned_weak bucket only (3/4 agree)
REM    [3] both   = combined (>=3/4 agree)
REM  Each bar the REAL model actually skipped is forced into a trade in the
REM  HTF-consensus direction (bypassing win_prob + all soft filters) IF it
REM  qualifies for that bucket; every REAL BUY/SELL is suppressed so each
REM  run's Total R is 100% attributable to previously-skipped bars only --
REM  read it as "missed profit", not a real/tradeable strategy result.
REM
REM  WARNING: this is a long run (12 weekly retrains x 3 shadow configs =
REM  36 retrain+backtest cycles, similar cost to the original A/B WFO TEST
REM  run x3).
REM
REM  SAFE BY DESIGN: weekly retrains go to data\models\test_workspace
REM  (QGAI_MODELS_DIR), never touching data\models\final -- your live model
REM  is never touched, live bridge can run at the same time.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"

cd /d "%ROOT%\engine"

echo ============================================================
echo   SHADOW-SKIPS MISSED-PROFIT DIAGNOSTIC - FULL (12 weeks x 3 modes)
echo   %DATE% %TIME%
echo   WARNING: long run - 36 retrain+backtest cycles total.
echo ============================================================

echo.
echo [1/3] shadow mode = strong (aligned_strong, 4/4 HTF agreement)...
set "QGAI_SHADOW_SKIPS=strong"
"%PY%" run_wfo.py --start 2026-04-06 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir shadowskips_wfo_FULL_strong
if errorlevel 1 goto fail

echo.
echo [2/3] shadow mode = weak (aligned_weak, 3/4 HTF agreement)...
set "QGAI_SHADOW_SKIPS=weak"
"%PY%" run_wfo.py --start 2026-04-06 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir shadowskips_wfo_FULL_weak
if errorlevel 1 goto fail

echo.
echo [3/3] shadow mode = both (>=3/4 HTF agreement, combined)...
set "QGAI_SHADOW_SKIPS=both"
"%PY%" run_wfo.py --start 2026-04-06 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir shadowskips_wfo_FULL_both
if errorlevel 1 goto fail
set "QGAI_SHADOW_SKIPS="

echo.
echo ============================================================
echo   DONE. Read Total R (missed profit) from each:
echo     backtest\results\shadowskips_wfo_FULL_strong\_WFO_SUMMARY.txt
echo     backtest\results\shadowskips_wfo_FULL_weak\_WFO_SUMMARY.txt
echo     backtest\results\shadowskips_wfo_FULL_both\_WFO_SUMMARY.txt
echo   Compare against the REAL 12-week baseline (+32.5R, 207 trades):
echo     backtest\results\volhtfgate_wfo_TEST_A_off\_WFO_SUMMARY.txt
echo   A large POSITIVE R in "strong" = real missed profit from skipping
echo   aligned_strong bars -^> raise/soften the win_prob threshold there.
echo   A NEGATIVE or near-zero R = the model was right to skip them -^>
echo   current behavior is fine, no change needed.
echo ============================================================
pause
exit /b 0

:fail
set "QGAI_SHADOW_SKIPS="
echo *** FAILED %DATE% %TIME% ***
pause
exit /b 1
