@echo off
setlocal
chcp 65001 >nul
title QGAI - Feature Sweep TIER 2 - High-Probability Dropped (~20 features)

REM =====================================================================
REM  Imtiyaz spec 2026-07-13, night 2 of 3: restore each of ~20 DROPPED
REM  features one at a time (does adding it back help R? -> candidate to
REM  re-add, needs a combo-interference check same as PART-1's B3 lesson.
REM  No help? -> stays correctly dropped).
REM
REM  This tier = the SMMA-trend family (ts_trend_h1/h4/m15, ts_line_dist_pct,
REM  ts_aligned_htf, ts_adx_switch_trend, ts_flip_recent - directly relevant
REM  to the 2026-07-13 architecture-rethink finding), raw H1_ADX/M30_ADX,
REM  move_2hr, corr_imp_ratio, the OB/SR distance+strength features, and the
REM  trend/regime composites re-tested individually.
REM
REM  Run AFTER Run_FeatureSweep_Tier1_Active.bat (night 1) finishes.
REM  Leakage-guard-safe: QGAI_TRAIN_CUTOFF=2026-03-31, backtest 2026-04-01
REM  to 2026-06-29. Resume-safe (same as tier 1).
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
echo   FEATURE SWEEP - TIER 2: HIGH-PROBABILITY DROPPED (~20 features)
echo   %DATE% %TIME%
echo ============================================================

"%PY%" run_feature_sweep.py --tier high_prob
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   TIER 2 DONE. Results: backtest\results\feature_sweep\high_prob_SUMMARY.csv
echo   Models built in: data\models\test_workspace (not your live model)
echo   Next (night 3): Run_FeatureSweep_Tier3_Remaining.bat
echo ============================================================
pause
exit /b %RC%
