@echo off
setlocal
chcp 65001 >nul
title QGAI - LEGACY REDIRECT - FS67-03

set "ROOT=C:\QGAI"
echo ============================================================
echo   LEGACY RUNNER REDIRECT
echo ------------------------------------------------------------
echo   Old runner:
echo   Run_FeatureSweep_Tier2_HighProbability.bat
echo.
echo   Registry runner now used:
echo   feature_sweep_67\FS67-03_RUN_Tier2_HighProbability.bat
echo ============================================================

call "%ROOT%\backtest\_runners\feature_sweep_67\FS67-03_RUN_Tier2_HighProbability.bat"
exit /b %ERRORLEVEL%
