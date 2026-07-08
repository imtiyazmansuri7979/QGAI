@echo off
title QGAI - Ablation QUICK TEST (2 weeks)
REM Tests REMOVING the H1-alignment composite features (the #4 lead) by retraining
REM WITHOUT them and walk-forward testing. Compare to baseline (wfo_results +144R).
REM To also test volume, add ",volume" to QGAI_ABLATE below.
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ABLATE=h4_trending_h1_aligned,h4_h1_regime_score,ts_htf_agreement"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   ABLATION QUICK TEST (2 weeks) - removing:
echo   %QGAI_ABLATE%
echo   If the [ABLATE] line prints and 2 weeks complete, it works
echo   -> then run Run_Ablate_FULL.bat
echo ============================================================
echo.
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --fixed-lot 0.01 --results-dir wfo_ablate_h1 --weeks 2
echo.
pause
