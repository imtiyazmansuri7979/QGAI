@echo off
title QGAI - Data Updater
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - DATA UPDATE (fills all gaps from MT5)
echo   (mt5_data_updater.py)
echo ============================================================
echo.
"%PY%" mt5_data_updater.py
echo.
echo ============================================================
echo   Data update finished. Press any key to close.
echo ============================================================
pause >nul
