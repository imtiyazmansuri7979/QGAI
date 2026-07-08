@echo off
title QGAI - Shadow Paper-Trade Ledger
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - SHADOW PAPER-TRADE LEDGER
echo ------------------------------------------------------------
echo   Turns the bridge's real signals (signals_all.csv) into a
echo   full paper-trade ledger: entry/exit price, why-exit,
echo   $ and %% profit, R, and a real-vs-shadow flag.
echo   Writes logs\shadow_trades.csv. Safe (does NOT touch trading).
echo   Re-run any time to refresh.
echo ============================================================
echo.
"%PY%" shadow_ledger.py
echo.
echo ============================================================
echo   Done. View it: open  shadow.html  (via the dashboard server)
echo     http://localhost:8000/shadow.html
echo ============================================================
pause
