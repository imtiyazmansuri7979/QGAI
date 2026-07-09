@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title QGAI WFO Monthly - FULL (13mo)
cls

cd /d "%~dp0"

echo ============================================================
echo   QGAI WALK-FORWARD MONTHLY - FULL 13 MONTHS (~3 hours)
echo   MONTHLY retrain, expanding window, fixed-lot (clean R)
echo   buf 0.09%% / TP 4%% | Resume-safe
echo ============================================================
echo.

python run_wfo.py --start 2025-06-01 --end 2026-06-12 --buf 0.09 --tp-equity 4 --period month 

echo.
echo   DONE! See wfo_results\_WFO_SUMMARY.txt
notepad wfo_results\_WFO_SUMMARY.txt
pause
