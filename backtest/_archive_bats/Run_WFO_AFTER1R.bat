@echo off
title QGAI - Walk-Forward OOS (TRAIL after +1R)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   WFO  -  TRAIL-AFTER-1R  (trail starts only after +1R profit)
echo   Goal: stop trailing-out losers; only trail real winners.
echo   Output: engine\wfo_results_after1r\   Resume-safe. ~1.5-2 hrs.
echo ============================================================
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --trail-mode after1r --results-dir wfo_results_after1r
echo.
echo DONE. Send Claude: wfo_results_after1r\_WFO_SUMMARY.txt
pause
