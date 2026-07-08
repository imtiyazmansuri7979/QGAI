@echo off
title QGAI - Walk-Forward OOS (Breakeven-only)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   WFO  -  BREAKEVEN-ONLY  (at +1R move stop to entry, no further trail)
echo   Goal: protect capital but let winners run to FLIP.
echo   Output: engine\wfo_results_be\   Resume-safe. ~1.5-2 hrs.
echo ============================================================
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --trail-mode be --results-dir wfo_results_be
echo.
echo DONE. Send Claude: wfo_results_be\_WFO_SUMMARY.txt
pause
