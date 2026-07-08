@echo off
title QGAI - Reset Backtests
cd /d "C:\QGAI\backtest"
echo This deletes saved results so the next run starts fresh (re-runs all).
echo.
if exist results rmdir /s /q results
if exist ALL_RESULTS.txt del /q ALL_RESULTS.txt
echo Done - results cleared. Run  Run_All_Backtests.bat  to start fresh.
pause
