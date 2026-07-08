@echo off
title QGAI - Trail Sweep FULL (all 41 weeks x 6 modes)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   TRAIL SWEEP - FULL  (true 41-week walk-forward, all 6 modes)
echo ------------------------------------------------------------
echo   Each week: retrain ONCE on past data, then backtest all 6
echo   stop-trail modes (line/off/after1r/be/htf/regime) on that
echo   same model. ~2-3 hrs. RESUME-SAFE: if it stops, run again.
echo   Low memory (one backtest at a time).
echo   Results: backtest\results\sweep_<mode>\
echo ============================================================
echo.
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --fixed-lot 0.01 --sweep-trails
echo.
echo ============================================================
echo   DONE. Tell Claude "done" — results in:
echo     backtest\results\TRAIL_SWEEP_SUMMARY.txt
echo     backtest\results\sweep_<mode>\ALL_OOS_trades.csv
echo ============================================================
pause
