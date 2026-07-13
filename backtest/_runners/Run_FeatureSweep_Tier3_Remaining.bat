@echo off
setlocal
chcp 65001 >nul
title QGAI - Feature Sweep TIER 3 - Remaining Dropped (~19 features)

REM =====================================================================
REM  Imtiyaz spec 2026-07-13, night 3 of 3: restore each of the remaining
REM  ~19 DROPPED features one at a time (EMA200 variants, news-timing
REM  extras, volume/tick_volume, session flags, before_eia, is_dead_hour,
REM  is_ny_session, remaining OB in-zone flags, ts_aligned).
REM
REM  This completes the full 67-feature sweep: 27 active (tier 1) + 40
REM  dropped (tier 2 high-probability + tier 3 remaining, 20+19=39 -- one
REM  fewer than 40 because ts_trend_h1 appears once; check the tier lists
REM  in run_feature_sweep.py if recounting).
REM
REM  Run AFTER Run_FeatureSweep_Tier2_HighProbability.bat (night 2) finishes.
REM  Leakage-guard-safe: QGAI_TRAIN_CUTOFF=2026-03-31, backtest 2026-04-01
REM  to 2026-06-29. Resume-safe (same as tier 1/2).
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
echo   FEATURE SWEEP - TIER 3: REMAINING DROPPED (~19 features)
echo   %DATE% %TIME%
echo ============================================================

"%PY%" run_feature_sweep.py --tier remaining
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   ALL 3 TIERS DONE. Full-sweep summary CSVs:
echo     backtest\results\feature_sweep\active_SUMMARY.csv
echo     backtest\results\feature_sweep\high_prob_SUMMARY.csv
echo     backtest\results\feature_sweep\remaining_SUMMARY.csv
echo   Models built in: data\models\test_workspace (not your live model)
echo   Each row's total_r / delta_vs_baseline / pf / wr tells you whether
echo   that ONE feature helps, hurts, or does nothing - a 3-month screen
echo   only (per your own stage-gate doc). Anything interesting still
echo   needs 1-year + WFO before it's trusted.
echo ============================================================
pause
exit /b %RC%
