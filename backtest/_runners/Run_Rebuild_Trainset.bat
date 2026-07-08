@echo off
title QGAI - Rebuild trainset (full-history flip entries, live exit) [PARKED/LATER]
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   REBUILD TRAINSET (Option A) - PARKED until ideas confirmed
echo   Every 2-SMMA flip = candidate entry over 2022-2026, labeled
echo   under the live HTF exit. ~12,976 trades.
echo   Output: data\Back_testing_trainset_REBUILT.xlsx
echo   NOTE: do NOT adopt until the current-period ideas (relabel +
echo   regime-TP) pass WFO. Then A/B vs RELABELED via retrain + WFO.
echo ============================================================
echo.
"%PY%" rebuild_trainset.py
echo.
pause
