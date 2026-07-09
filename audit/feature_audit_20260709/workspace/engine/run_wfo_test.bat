@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title QGAI WFO - 4 week TEST
cls

cd /d "%~dp0"

echo ============================================================
echo   QGAI WALK-FORWARD - 4 WEEK TEST (~1 hour, verify first)
echo   Expanding window, weekly retrain (core-only), Jun 2025+
echo   Resume-safe: completed weeks skipped
echo ============================================================
echo.

python run_wfo.py --start 2025-06-01 --end 2026-06-12 --buf 0.09 --tp-equity 4 --weeks 4

echo.
echo   DONE! See wfo_results\_WFO_SUMMARY.txt
notepad wfo_results\_WFO_SUMMARY.txt
pause
