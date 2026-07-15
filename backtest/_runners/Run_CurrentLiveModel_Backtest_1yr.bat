@echo off
setlocal
chcp 65001 >nul
title QGAI - Current LIVE Model (27+hmm=28 feat) - 1yr Backtest

REM =====================================================================
REM  Imtiyaz (2026-07-14): "i final it after ablation test" - the model
REM  currently in data\models\final (retrained today 07:27, 27 active
REM  features + hmm_state = 28 saved) was DELIBERATELY finalized after an
REM  ablation-test run, not an accidental overwrite. Confirmed: current
REM  engine/features.py FEATURE_COLS = 27, matches exactly.
REM
REM  This bat backtests THAT model AS-IS - no retrain, read-only, points
REM  directly at data\models\final. Same 1-year window as other honest
REM  1yr backtests (2025-06-29 -> 2026-06-29) for comparability.
REM
REM  NOTE: this is a SINGLE-MODEL backtest, not WFO. The current live
REM  model's own training data (through ~2026-04-29) overlaps most of this
REM  1-year window, so it is EXPECTED to be partly in-sample (optimistic) -
REM  --allow-in-sample is passed deliberately (the leakage_guard would
REM  otherwise correctly block it). Read this as "how does the CURRENT
REM  model behave on recent history", NOT proof of live-forward performance.
REM  For an honest true-OOS number, see the WFO companion bat:
REM  Run_CurrentLiveModel_WFO_FULL.bat (retrains fresh each week).
REM
REM  SAFE: read-only, no retrain, does not touch any model file.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT=C:\QGAI\backtest\results\current_live_28feat_backtest_1yr_20260714"

cd /d "%ROOT%\engine"

echo ============================================================
echo   CURRENT LIVE MODEL (27+hmm=28 feat) - 1yr BACKTEST
echo   %DATE% %TIME%
echo   NOTE: in-sample (model trained through ~2026-04-29) - sanity/
echo   reference only, not an OOS proof. See WFO bat for the honest number.
echo ============================================================

"%PY%" "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --allow-in-sample --out-dir "%OUT%"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   DONE %DATE% %TIME%
echo   Report: %OUT%\backtest_report.txt  (read the Total R)
echo   Reminder: in-sample result, reference only.
echo ============================================================
pause
exit /b 0

:fail
echo.
echo *** FAILED %DATE% %TIME% ***
pause
exit /b 1
