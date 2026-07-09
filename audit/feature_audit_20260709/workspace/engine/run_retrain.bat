@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title QGAI - RETRAIN (new OB features)
cls

cd /d "%~dp0"

echo ============================================================
echo   QGAI RETRAIN - 8 new direction-aware OB S/R features
echo   (5 old OB dist features removed)
echo   This trains: combined, buy, sell, ranging, trending, volatile
echo   ~30-60 min depending on machine
echo ============================================================
echo.
echo Starting retrain...
echo.

python train.py > retrain_log.txt 2>&1

if errorlevel 1 (
    echo.
    echo  *** RETRAIN FAILED *** - see retrain_log.txt
    notepad retrain_log.txt
    pause
    exit /b 1
)

echo.
echo  RETRAIN DONE! Models saved.
echo  Log: retrain_log.txt
echo.
echo  Next: run backtest to test new features
notepad retrain_log.txt
pause
