@echo off
setlocal
chcp 65001 >nul
title QGAI - LEGACY REDIRECT - FS67-04

set "ROOT=C:\QGAI"
echo ============================================================
echo   LEGACY RUNNER REDIRECT
echo ------------------------------------------------------------
echo   Old runner:
echo   Run_FeatureSweep_Tier3_Remaining.bat
echo.
echo   Registry runner now used:
echo   feature_sweep_67\FS67-04_RUN_Tier3_Remaining.bat
echo ============================================================

call "%ROOT%\backtest\_runners\feature_sweep_67\FS67-04_RUN_Tier3_Remaining.bat"
exit /b %ERRORLEVEL%
