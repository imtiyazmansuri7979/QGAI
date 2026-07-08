@echo off
title QGAI - Walk-Forward OOS (REGIME-based trailing)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   WFO  -  REGIME-BASED TRAILING  (data-backed)
echo ------------------------------------------------------------
echo   Ranging  -> trail OFF  (TRAIL avgR -0.10; let FLIP exit +0.26)
echo   Trending -> trail OFF  (TRAIL avgR -0.05; let FLIP exit +0.22)
echo   Volatile -> trail ON   (TRAIL avgR +0.05; lock gains in noise)
echo   Output: engine\wfo_results_regime\   Resume-safe. ~1.5-2 hrs.
echo ============================================================
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --trail-mode regime --results-dir wfo_results_regime
echo.
echo DONE. Send Claude: wfo_results_regime\_WFO_SUMMARY.txt
pause
