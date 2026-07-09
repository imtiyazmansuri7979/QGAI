@echo off
title QGAI Dashboard Server
color 0B
cls

set "ENGINE_DIR=%~dp0"

echo ============================================================
echo   QGAI Dashboard Server  (FIX #12: handles /mode + /feedback)
echo   Keep this window open while trading
echo ============================================================
echo.
echo Starting server at http://localhost:8000
echo Open browser: http://localhost:8000/dashboard.html
echo.
cd /d "%ENGINE_DIR%"
python serve.py
pause
