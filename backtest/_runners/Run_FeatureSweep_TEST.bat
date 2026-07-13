@echo off
setlocal
chcp 65001 >nul
title QGAI - Feature Sweep TEST (2 features, quick sanity check)

REM =====================================================================
REM  Imtiyaz spec 2026-07-13: before committing to the full 67-feature,
REM  3-4-night sweep, run a SHORT test (2 features from the active tier)
REM  to verify the whole loop works - train, backtest, leakage-guard,
REM  result parsing, resume-cache - before the long overnight runs.
REM
REM  Uses engine/run_feature_sweep.py. Every feature = 1 real retrain +
REM  1 real 3-month backtest (leakage-guard-safe: QGAI_TRAIN_CUTOFF=
REM  2026-03-31, backtest 2026-04-01 to 2026-06-29).
REM
REM  SAFE BY DESIGN (2026-07-13, root-cause fix after 3 same-day model-loss
REM  incidents): every retrain in this sweep goes to a SEPARATE folder,
REM  data\models\test_workspace, via the QGAI_MODELS_DIR override
REM  (engine/config.py). data\models\final (your live model) is NEVER
REM  touched by this script - no backup/restore needed, the live bridge can
REM  even be running at the same time without any conflict.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

echo ============================================================
echo   FEATURE SWEEP - TEST (2 active features + baseline)
echo   %DATE% %TIME%
echo ============================================================

"%PY%" run_feature_sweep.py --tier active --limit 2
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   DONE. Check: backtest\results\feature_sweep\active_SUMMARY.csv
echo   Models built in: data\models\test_workspace (not your live model)
echo   If this looks right, run the full tiers:
echo     Run_FeatureSweep_Tier1_Active.bat
echo     Run_FeatureSweep_Tier2_HighProbability.bat
echo     Run_FeatureSweep_Tier3_Remaining.bat
echo ============================================================
pause
exit /b %RC%
