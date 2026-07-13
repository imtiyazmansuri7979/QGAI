@echo off
setlocal
chcp 65001 >nul
title QGAI - Feature Sweep TIER 1 - Active (27 features)

REM =====================================================================
REM  Imtiyaz spec 2026-07-13, night 1 of 3: ablate each of the 27 currently
REM  ACTIVE features one at a time (does removing it hurt R? -> it matters,
REM  keep it. No change/improves? -> candidate to drop).
REM
REM  Uses engine/run_feature_sweep.py --tier active (full 27, priority =
REM  current feature_importance.csv ranking, most important first).
REM  Leakage-guard-safe: QGAI_TRAIN_CUTOFF=2026-03-31, backtest 2026-04-01
REM  to 2026-06-29 (clean 3-month OOS window).
REM
REM  Resume-safe: run Run_FeatureSweep_TEST.bat first to confirm the loop
REM  works. If this run is interrupted, re-running it skips everything
REM  already cached (result.json present) and continues where it left off.
REM
REM  SAFE BY DESIGN (2026-07-13, root-cause fix after 3 same-day model-loss
REM  incidents): every retrain goes to data\models\test_workspace (separate
REM  from data\models\final) via QGAI_MODELS_DIR. Your live model is NEVER
REM  touched - no need to close the live bridge, no backup/restore step.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

echo ============================================================
echo   FEATURE SWEEP - TIER 1: ACTIVE (27 features)
echo   %DATE% %TIME%
echo ============================================================

"%PY%" run_feature_sweep.py --tier active
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   TIER 1 DONE. Results: backtest\results\feature_sweep\active_SUMMARY.csv
echo   Models built in: data\models\test_workspace (not your live model)
echo   Next (night 2): Run_FeatureSweep_Tier2_HighProbability.bat
echo ============================================================
pause
exit /b %RC%
