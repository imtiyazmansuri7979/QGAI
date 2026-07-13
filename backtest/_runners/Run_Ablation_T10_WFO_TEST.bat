@echo off
setlocal
chcp 65001 >nul
title QGAI - Ablation T10 WFO TEST (2 weeks)

REM =====================================================================
REM  Ablation T10: REMOVE trend-signal features (ts_bars_since_flip,
REM  ts_htf_agreement) via QGAI_ABLATE env var.
REM  WFO SHORT TEST — 2 weeks only — verify no crash.
REM  Then run the FULL WFO bat.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ABLATE=ts_bars_since_flip,ts_htf_agreement"

cd /d "%ROOT%\engine"

echo ============================================================
echo   ABLATION T10 WFO - TEST (2 weeks)
echo   Removed: ts_bars_since_flip, ts_htf_agreement
echo   Output: backtest\results\ablation_T10_wfo_TEST
echo ============================================================
echo.

"%PY%" run_wfo.py --start 2026-06-01 --end 2026-06-15 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir ablation_T10_wfo_TEST

if errorlevel 1 (
    echo *** FAILED — check error above ***
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   WFO TEST DONE.
echo   If OK, run Run_Ablation_T10_WFO.bat (full year)
echo ============================================================
pause
