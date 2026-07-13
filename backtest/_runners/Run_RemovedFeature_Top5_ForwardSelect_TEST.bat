@echo off
setlocal
chcp 65001 >nul
title QGAI - Top 5 Removed Features Forward Selection TEST

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT=C:\QGAI\backtest\_scripts\forward_select_removed_features.py"

echo ============================================================
echo   TOP 5 REMOVED FEATURES - SMART FORWARD SELECTION
echo ------------------------------------------------------------
echo   B0 = baseline current 27
echo   Then each candidate is tested as:
echo     accepted features + next candidate
echo.
echo   If Total R improves, candidate is kept.
echo   If Total R drops, candidate is put aside and NOT used later.
echo.
echo   WARNING: close live bridge before running.
echo   The script temporarily retrains data\models\final, then restores it.
echo ============================================================
echo.

cd /d "%ROOT%"
"%PY%" "%SCRIPT%"
if errorlevel 1 (
    echo.
    echo FORWARD SELECTION FAILED
    pause
    exit /b 1
)

echo.
echo DONE. Results:
echo   C:\QGAI\backtest\results\removed_feature_top5_FORWARD_SELECT_TEST
echo.
pause
exit /b 0
