@echo off
title QGAI - Walk-Forward OOS (H1-line trail)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   WFO  -  H1-LINE TRAIL  (trail the slower H1 ratchet line, not M15)
echo   Goal: fewer premature TRAIL exits (wider, slower trail).
echo   Output: engine\wfo_results_htftrail\   Resume-safe. ~1.5-2 hrs.
echo ============================================================
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --trail-mode htf --results-dir wfo_results_htftrail
echo.
echo DONE. Send Claude: wfo_results_htftrail\_WFO_SUMMARY.txt
pause
