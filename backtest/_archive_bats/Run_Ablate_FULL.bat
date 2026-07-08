@echo off
title QGAI - Ablation FULL (41 weeks, remove H1-alignment)
REM Full walk-forward with the H1-alignment composites REMOVED. Resume-safe.
REM Compare result (wfo_ablate_h1) to baseline (wfo_results +144R, PF 1.55):
REM   keep the removal ONLY if totalR / PF / green-weeks IMPROVE.
REM To also test volume removal, add ",volume" to QGAI_ABLATE.
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ABLATE=h4_trending_h1_aligned,h4_h1_regime_score,ts_htf_agreement"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   ABLATION FULL - removing: %QGAI_ABLATE%
echo   ~10-13 hrs, resume-safe. Results: backtest\results\wfo_ablate_h1\
echo   WARNING: overwrites data\models\final each week (clobbers the
echo   demo model). After testing, run 3_Train_Models.bat to rebuild
echo   the production model (no ablation).
echo ============================================================
echo.
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --fixed-lot 0.01 --results-dir wfo_ablate_h1
echo.
echo Done. Tell Claude "ablation done" to compare vs baseline.
pause
