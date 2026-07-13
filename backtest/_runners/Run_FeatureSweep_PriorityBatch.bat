@echo off
setlocal
chcp 65001 >nul
title QGAI - Feature Sweep PRIORITY BATCH (10 features, run first)

REM =====================================================================
REM  Imtiyaz's exact "first batch to test" list (2026-07-13, detailed
REM  3-stage sweep plan). Mixed active + dropped features on purpose:
REM    h4_support_dist, h1_resist_dist, move_2hr, ts_line_dist_pct,
REM    tick_volume, H4_DI_diff, h4_adx_slope, move_4hr,
REM    momentum_aligned_2hr, h1_support_dist
REM
REM  Each one is auto-routed by run_feature_sweep.py: currently-ACTIVE
REM  features (H4_DI_diff, h4_adx_slope, move_4hr, momentum_aligned_2hr)
REM  get ABLATED (removed, compare vs baseline); currently-DROPPED features
REM  (the other 6, including tick_volume -- tested RAW, no normalization,
REM  no hard rule, model decides) get UNPRUNED (restored, compare vs
REM  baseline).
REM
REM  Also computes, per feature: BUY vs SELL breakdown, Ranging/Trending/
REM  Volatile breakdown, week-by-week consistency, and an automated
REM  verdict (CORE_KEEP / DROP_CANDIDATE / NEEDS_1YEAR_CONFIRMATION /
REM  CONFIRMED_DROPPED / NEUTRAL_REDUNDANT / REVIEW) -- a verdict other
REM  than NEUTRAL_REDUNDANT or CONFIRMED_DROPPED still needs Stage 2
REM  (1-year) + Stage 3 (WFO) before it's trusted, per your own stage-gate.
REM
REM  SAFE BY DESIGN: every retrain goes to data\models\test_workspace
REM  (separate from data\models\final) via QGAI_MODELS_DIR. Your live
REM  model is NEVER touched - the live bridge can run at the same time.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

echo ============================================================
echo   FEATURE SWEEP - PRIORITY BATCH (10 features)
echo   %DATE% %TIME%
echo ============================================================

"%PY%" run_feature_sweep.py --tier priority_batch
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   DONE. Results: backtest\results\feature_sweep\priority_batch_SUMMARY.csv
echo   Models built in: data\models\test_workspace (not your live model)
echo   Next: Run_FeatureSweep_Tier1_Active.bat (Day 1, full active tier)
echo ============================================================
pause
exit /b %RC%
