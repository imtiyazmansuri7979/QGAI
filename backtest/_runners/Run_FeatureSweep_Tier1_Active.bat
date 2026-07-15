@echo off
setlocal
chcp 65001 >nul
title QGAI - LEGACY REDIRECT - FS67-02

set "ROOT=C:\QGAI"
echo ============================================================
echo   LEGACY RUNNER REDIRECT
echo ------------------------------------------------------------
echo   Old runner:
echo   Run_FeatureSweep_Tier1_Active.bat
echo.
echo   Registry runner now used:
echo   feature_sweep_67\FS67-02_RUN_Tier1_Active.bat
echo ============================================================

call "%ROOT%\backtest\_runners\feature_sweep_67\FS67-02_RUN_Tier1_Active.bat"
exit /b %ERRORLEVEL%
