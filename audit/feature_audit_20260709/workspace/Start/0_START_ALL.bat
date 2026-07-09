@echo off
setlocal
chcp 65001 >nul
title QGAI - START ALL (one-click full system)

REM =====================================================================
REM  QGAI — ONE-CLICK START ALL
REM  Runs the whole system so EVERY dashboard tab has fresh data:
REM    1. Update market data           (mt5_data_updater.py)   [one-shot]
REM    2. Refresh chart data           (chart_live_ohlc/chart_data) [one-shot]
REM    3. Refresh shadow ledger        (shadow_ledger.py)      [one-shot]
REM    4. Rebuild signal log           (build_signal_log.py)   [one-shot]
REM    5. Start LIVE trading bridge    (bridge_main.py)   [own window, minimized]
REM    6. Start dashboard server       (serve.py :8000)   [own window, minimized]
REM    7. Open the dashboard in the browser
REM
REM  ⚠️ COLD START only — run this when NOTHING is running yet. If the
REM     bridge/server are already up, DON'T run this (would double-start).
REM     For individual pieces use 1..7_*.bat as before.
REM =====================================================================

set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "ENG=C:\QGAI\engine"

cd /d "%ENG%"

echo ============================================================
echo   QGAI — STARTING FULL SYSTEM   %DATE% %TIME%
echo ============================================================

echo [1/7] Updating market data...
"%PY%" mt5_data_updater.py
if errorlevel 1 echo   (data update had a warning — continuing)

echo [2/7] Refreshing chart data...
"%PY%" chart_live_ohlc.py 1500
"%PY%" chart_data.py 1200

echo [3/7] Refreshing shadow ledger...
"%PY%" shadow_ledger.py

echo [4/7] Rebuilding signal log (all dashboard tabs)...
"%PY%" build_signal_log.py ..\backtest\results\fullhistory_regime

echo [5/7] Starting LIVE trading bridge (own window)...
start "QGAI Bridge" /min cmd /k "cd /d %ENG% && set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& "%PY%" bridge_main.py"

echo [6/7] Starting dashboard server :8000 (own window)...
start "QGAI Dashboard Server" /min cmd /k "cd /d %ENG% && set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& "%PY%" serve.py"

echo [7/7] Opening dashboard in browser...
timeout /t 3 >nul
start "" http://localhost:8000/dashboard.html

echo.
echo ============================================================
echo   ALL STARTED. Two minimized windows are running:
echo     - QGAI Bridge            (live trading)
echo     - QGAI Dashboard Server  (port 8000)
echo   Dashboard opened in your browser. All tabs have fresh data.
echo   To STOP: close those two windows (Ctrl+C in each).
echo ============================================================
echo.
echo This launcher window can be closed now.
pause
exit /b 0
