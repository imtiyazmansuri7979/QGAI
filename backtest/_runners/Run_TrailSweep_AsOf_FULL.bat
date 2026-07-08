@echo off
title QGAI - FIX-2 TRAIL SWEEP FULL : 53 weeks, all 6 trail modes, as-of data
REM ---------------------------------------------------------------------------
REM Run Run_TrailSweep_AsOf_TEST.bat FIRST (house rule). ~2-3 hrs, resume-safe.
REM One retrain per week shared by all 6 trail modes (line/off/after1r/be/htf/
REM regime) on the leak-free as-of workdir with the deployed rel HMM.
REM Results: backtest\results\sweepasof_<mode>\ + SWEEPASOF_SUMMARY.txt/.csv
REM DECISION (profit-first): adopt the mode with highest total R, ONLY if it
REM beats the current mode (htf) - gate = new honest baseline +393.7R world.
REM Live untouched; safe to run while the DEMO bridge trades.
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ROOT=C:\QGAI_wfo_asof_rel"
set "QGAI_HMM_VARIANT=rel"
cd /d "C:\QGAI\engine"
if not exist "C:\QGAI_wfo_asof_rel\data\merged\adx_merged.csv" (echo workdir missing - run the TEST bat first & pause & exit /b 1)
"%PY%" run_wfo.py --sweep-trails --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --results-dir sweepasof
echo.
echo DONE. Tell Claude: "trail sweep done" to analyze SWEEPASOF_SUMMARY.csv
echo vs the current htf mode (profit-first, gate vs +393.7R world).
pause
