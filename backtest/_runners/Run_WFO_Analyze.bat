@echo off
title QGAI - WFO $10k Weekly/Monthly Analysis
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\backtest"
echo ============================================================
echo   QGAI - WFO OOS ANALYSIS  ($10,000 dynamic-compounding)
echo   Summary + MONTHLY + WEEKLY breakdown from the full WFO run.
echo   Reads: backtest\results\wfo_results\ALL_OOS_trades.csv
echo ============================================================
echo.
"%PY%" wfo_analyze.py
echo.
echo ============================================================
echo   Saved: wfo_results\WFO_MONTHLY.csv | WFO_WEEKLY.csv
echo          wfo_results\WFO_ACCOUNT_10k.csv (per-trade)
echo ============================================================
pause
