@echo off
title QGAI - FIX-3 : weekly shadow-vs-backtest reconciliation (scaling gate)
REM ---------------------------------------------------------------------------
REM Run this ONCE A WEEK while the DEMO bridge trades (first run makes sense
REM after ~1 week of demo so shadow_trades.csv has fresh rows).
REM Backtests the last 7 days with the CURRENT live models, then compares the
REM trades vs the live shadow log. One folder: results\reconcile_<date>\
REM GATE before scaling capital: 4-8 straight weeks with high entry overlap,
REM similar exit mix, weekly R gap within +/-20 percent.
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
"%PY%" weekly_reconcile.py
echo.
echo DONE. Open results\reconcile_<today>\reconcile_summary.csv
echo Tell Claude "reconcile done" for analysis vs the +/-20 percent gate.
pause
