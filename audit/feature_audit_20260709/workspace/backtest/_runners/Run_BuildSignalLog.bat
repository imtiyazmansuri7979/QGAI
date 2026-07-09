@echo off
title QGAI - Build COMPLETE Signal Log (full-history regime-TP + live)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - BUILD COMPLETE SIGNAL LOG
echo   Merges the full-history REGIME-TP backtest (every M15 bar
echo   2022-2026 + $ move/result) with the LIVE log (real signals
echo   + real outcome/$ move) -^> logs\signals_complete.csv
echo   The dashboard Signal Log reads this (history + live, merged;
echo   live always overrides for the same bar).
echo ============================================================
echo.
"%PY%" build_signal_log.py "..\backtest\results\fullhistory_regime"
echo.
echo ============================================================
echo   Done. Restart 5_Dashboard.bat (or just reload) to see it.
echo   Re-run this only to refresh the HISTORY part; the LIVE part
echo   updates by itself in the dashboard every 15s.
echo ============================================================
pause
