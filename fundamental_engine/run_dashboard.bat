@echo off
chcp 65001 >nul
title Gold Fundamental Dashboard

echo ======================================================================
echo  GOLD FUNDAMENTAL DASHBOARD
echo  http://localhost:5000
echo ======================================================================
echo.
echo Checking Flask...
pip install flask --quiet 2>nul
echo.
echo Opening browser and starting dashboard...
echo Press Ctrl+C to stop.
echo.

cd /d C:\QGAI\fundamental_engine
start "" "http://localhost:5000"
python dashboard.py

pause
