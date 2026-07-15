@echo off
setlocal
chcp 65001 >nul
title QGAI - Current LIVE Model config (27+hmm=28 feat) - FULL WFO (53 weeks)

REM =====================================================================
REM  Imtiyaz (2026-07-14): honest 53-week WFO of the CURRENT live feature
REM  config (27 active features in engine\features.py today, + hmm_state
REM  = 28 saved - the config "finalized after ablation test"). Unlike the
REM  1yr single-model backtest companion bat, this is the TRUE honest
REM  number: run_wfo.py retrains fresh from CURRENT features.py code every
REM  week, strictly before that week's test window (leakage-guard-safe).
REM
REM  Compare Total R here against:
REM    - the pre-ablation honest baseline (~+80-86R/53wk, W12/W13 -
REM      see backtest\results\_LEAKAGE_FIX_COMPARISON\SUMMARY.md)
REM    - the current live period (2026-04-06 -> 06-29, +32.5R/12wk,
REM      backtest\results\volhtfgate_wfo_TEST_A_off)
REM
REM  ~2-3 hours. Resume-safe.
REM
REM  SAFE BY DESIGN: every weekly fold retrain goes to the isolated
REM  data\models\test_workspace folder (QGAI_MODELS_DIR), NEVER touching
REM  data\models\final - today's finalized live model is untouched
REM  throughout this run, live bridge can keep running at the same time.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"

cd /d "%ROOT%\engine"

echo ============================================================
echo   CURRENT LIVE MODEL CONFIG (27+hmm=28 feat) - FULL WFO (53 weeks)
echo   SAFE: retrains go to data\models\test_workspace, live model untouched.
echo   %DATE% %TIME%
echo   WARNING: this is a long run (53 weekly retrains, ~2-3 hours).
echo ============================================================

"%PY%" run_wfo.py --start 2025-06-23 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir wfo_current_live_28feat_20260714
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   DONE %DATE% %TIME%
echo   Results: backtest\results\wfo_current_live_28feat_20260714\
echo   Compare Total R (_WFO_SUMMARY.txt) against the ~+80-86R honest
echo   baseline (W12/W13) and the +32.5R/12wk current-period run.
echo   (No revert needed - retrains stayed in test_workspace.)
echo ============================================================
pause
exit /b 0

:fail
echo.
echo *** FAILED %DATE% %TIME% ***
echo   (No live-model restore needed - retrains stayed in test_workspace.)
pause
exit /b 1
