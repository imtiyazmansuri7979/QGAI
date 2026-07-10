@echo off
title QGAI Dashboard Server
color 0B
chcp 65001 >nul
cls

set "ENGINE_DIR=%~dp0"

echo ============================================================
echo   QGAI Dashboard Server  (handles /mode + /feedback)
echo   Keep this window open while trading
echo ============================================================
echo.
echo Starting server at http://localhost:8000
echo Open browser: http://localhost:8000/dashboard.html
echo.
cd /d "%ENGINE_DIR%"
python serve.py
echo.
echo Dashboard server stopped.
pause
