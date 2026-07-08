@echo off
title QGAI - Auto Scheduler (Daily data + Monday retrain + Bridge)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - FULL AUTO SCHEDULER  (scheduler.py)
echo ------------------------------------------------------------
echo   Leave this window OPEN. It runs everything automatically:
echo     * On start : data update + start trading bridge
echo     * Broker 01:30 daily : data update
echo     * Broker 07:30 Monday: retrain models (weekly)
echo     * Broker 23:55 daily : stop bridge + daily report
echo   Ctrl+C to stop.
echo ============================================================
echo.
"%PY%" scheduler.py
echo.
echo ============================================================
echo   Scheduler stopped. Press any key to close.
echo ============================================================
pause >nul
