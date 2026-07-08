@echo off
title QGAI - Walk-Forward OOS (FLIP-ONLY, no trail)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - WALK-FORWARD OOS  -  FLIP-ONLY (no stop-trail)
echo ------------------------------------------------------------
echo   Tests removing the TRAIL exit: the stop stays at its initial
echo   level (no upward trail), so trades exit only on FLIP / initial
echo   SL / TP. Goal: recover the net-negative TRAIL exits (-7R).
echo.
echo   Writes to:  engine\wfo_results_fliponly\
echo   (your wfo_results\ and wfo_results_ratchet\ are kept.)
echo   RESUME-SAFE. Full year ~1.5-2 hrs.
echo ============================================================
echo.
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --no-trail --results-dir wfo_results_fliponly
echo.
echo ============================================================
echo   DONE. Compare with the trail version - send Claude the file
echo   wfo_results_fliponly\_WFO_SUMMARY.txt
echo ============================================================
pause
