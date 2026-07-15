@echo off
setlocal
chcp 65001 >nul
title QGAI - Shadow-Skips Missed-Profit Diagnostic (TEST, 2 weeks)

REM =====================================================================
REM  Imtiyaz's follow-up (2026-07-14) to the win_prob calibration diagnostic
REM  and the HTF-alignment skip-rate diagnostic:
REM  "of the trades we did NOT take, how many would have been profitable?"
REM
REM  This is a COUNTERFACTUAL run using engine/backtest_replay.py's new
REM  QGAI_SHADOW_SKIPS env override (default unset = zero effect on any
REM  normal backtest -- verified by py_compile + code review, no other
REM  behavior touched):
REM    - every bar the REAL model skipped is checked against the SAME 4
REM      HTF-direction signals as the skip-rate diagnostic (H1/H4 ADX-DI +
REM      H1/H4 SMMA-trend). If they agree strongly enough (see MODE below),
REM      the bar is FORCED into a trade in that direction -- bypassing the
REM      win_prob gate AND all soft filters -- then simulated with the
REM      SAME SL/TP/trailing/ratchet rules as every real trade.
REM    - every bar that was a REAL BUY/SELL is SUPPRESSED to SKIP, so this
REM      run's Total R is 100% attributable to previously-skipped bars --
REM      directly comparable against 0 (no missed profit) rather than mixed
REM      with real-trade P&L.
REM
REM  MODE (QGAI_SHADOW_SKIPS):
REM    strong = only 4/4 HTF-signal agreement (Imtiyaz's exact "aligned_strong"
REM             bucket from the calibration diagnostic)
REM    weak   = only 3/4 agreement ("aligned_weak" bucket)
REM    both   = 3/4 or 4/4 (both buckets combined)
REM
REM  THIS IS A SANITY TEST ONLY (2 weeks, house TEST-RUN-FIRST rule) --
REM  checks for crashes and confirms the report/CSV files appear correctly
REM  before committing to the full 12-week run (Run_ShadowSkips_MissedProfit_FULL.bat).
REM  A small sample here is NOT meaningful on its own -- do not draw
REM  conclusions from this run's R number.
REM
REM  READ-ONLY / SAFE: weekly retrains go to data\models\test_workspace
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
echo   SHADOW-SKIPS MISSED-PROFIT DIAGNOSTIC - TEST (2 weeks)
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [TEST] shadow mode = strong (aligned_strong bucket only)...
set "QGAI_SHADOW_SKIPS=strong"
"%PY%" run_wfo.py --start 2026-06-15 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir shadowskips_wfo_TEST_strong
if errorlevel 1 goto fail
set "QGAI_SHADOW_SKIPS="

echo.
echo ============================================================
echo   DONE. Check for crashes, then read:
echo     backtest\results\shadowskips_wfo_TEST_strong\backtest_report.txt
echo     backtest\results\shadowskips_wfo_TEST_strong\_WFO_SUMMARY.txt
echo   Total R there = counterfactual missed profit from aligned_strong SKIPs
echo   over this 2-week window (small sample, sanity check only).
echo   If clean -^> run Run_ShadowSkips_MissedProfit_FULL.bat (12 weeks,
echo   matches the volhtfgate_wfo_TEST_A_off period for apples-to-apples).
echo ============================================================
pause
exit /b 0

:fail
set "QGAI_SHADOW_SKIPS="
echo *** FAILED %DATE% %TIME% ***
pause
exit /b 1
