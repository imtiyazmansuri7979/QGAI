@echo off
setlocal
chcp 65001 >nul
title QGAI - LEGACY REDIRECT - FS67-01

set "ROOT=C:\QGAI"
echo ============================================================
echo   LEGACY RUNNER REDIRECT
echo ------------------------------------------------------------
echo   Old runner:
echo   Run_FeatureSweep_PriorityBatch.bat
echo.
echo   Registry runner now used:
echo   feature_sweep_67\FS67-01_RUN_PriorityBatch.bat
echo ============================================================

call "%ROOT%\backtest\_runners\feature_sweep_67\FS67-01_RUN_PriorityBatch.bat"
exit /b %ERRORLEVEL%
