@echo off
title QGAI - Start Trading (Live Bridge)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - STARTING LIVE TRADING BRIDGE
echo   (bridge_main.py)  -  Ctrl+C to stop
echo ============================================================
echo.
"%PY%" bridge_main.py
echo.
echo ============================================================
echo   Bridge stopped. Press any key to close this window.
echo ============================================================
pause >nul
