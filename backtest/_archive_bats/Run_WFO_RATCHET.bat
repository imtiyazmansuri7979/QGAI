@echo off
title QGAI - Walk-Forward OOS (RATCHET daily rule)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - WALK-FORWARD OOS  -  RATCHET daily rule version
echo ------------------------------------------------------------
echo   Same full walk-forward, but the backtest now uses the new
echo   RATCHET daily stop (loss-floor -9% + profit-lock trailing
echo   9%% below the day's peak).
echo.
echo   Writes to a SEPARATE folder:  engine\wfo_results_ratchet\
echo   (your old fixed-9%% run in wfo_results\ is kept untouched).
echo   RESUME-SAFE: if it stops, run again - it continues.
echo   Full year ~1.5-2 hrs.
echo ============================================================
echo.
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --results-dir wfo_results_ratchet
echo.
echo ============================================================
echo   DONE. Analyze with (edit wfo_analyze.py TRADES path to
echo   wfo_results_ratchet\ALL_OOS_trades.csv, or tell Claude).
echo ============================================================
pause
