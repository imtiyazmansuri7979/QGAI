@echo off
title QGAI - Trail Sweep QUICK TEST (2 weeks)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   TRAIL SWEEP - QUICK TEST (first 2 weeks only)
echo   Confirms the all-6-modes sweep works before the full run.
echo   One retrain per week, then all 6 stop-trail modes on it.
echo   ~10 min. Low memory (one backtest at a time).
echo ============================================================
echo.
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --fixed-lot 0.01 --sweep-trails --weeks 2
echo.
echo ============================================================
echo   TEST DONE. If you see a SUMMARY table with 6 modes and
echo   real R numbers, the sweep works -> run Run_TrailSweep_FULL.bat
echo ============================================================
pause
