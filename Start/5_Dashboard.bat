@echo off
title QGAI - Dashboard Server
color 0B
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - DASHBOARD SERVER  (serve.py, port 8000)
echo ------------------------------------------------------------
echo   Keep this window OPEN while watching the dashboard.
echo   If closed, the page shows "Failed to fetch".
echo ============================================================
echo.
echo Opening browser: http://localhost:8000/dashboard.html
start "" http://localhost:8000/dashboard.html
echo.
"%PY%" serve.py
echo.
echo ============================================================
echo   Dashboard server stopped. Press any key to close.
echo ============================================================
pause >nul
