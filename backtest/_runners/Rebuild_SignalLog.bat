@echo off
setlocal
chcp 65001 >nul
title QGAI - Rebuild Signal Log (dashboard SIGNAL LOG refresh)

REM =====================================================================
REM  Rebuilds logs/signals_complete.csv = full-history backtest + live
REM  signals merged. Run this whenever the dashboard SIGNAL LOG looks
REM  stale (count stuck / recent live signals not showing).
REM  The LIVE part (signals_all.csv) is real-time; this merges it into
REM  the historical file the dashboard reads.
REM =====================================================================

set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

cd /d "C:\QGAI\engine"

echo Rebuilding signals_complete.csv (backtest + live merge)...
"%PY%" build_signal_log.py ..\backtest\results\fullhistory_regime
if errorlevel 1 (
  echo.
  echo *** FAILED — check the message above. ***
  pause
  exit /b 1
)

echo.
echo DONE. Refresh the dashboard (F5) to see the updated SIGNAL LOG.
pause
exit /b 0
