@echo off
setlocal
chcp 65001 >nul
title QGAI - Ablation T10 WFO FULL (53 weeks)

REM =====================================================================
REM  Ablation T10: REMOVE trend-signal features (ts_bars_since_flip,
REM  ts_htf_agreement) via QGAI_ABLATE env var.
REM  FULL WFO — 53 weeks, weekly retrain, true OOS.
REM  GATE: >= +80.5R (current NO-VOLUME baseline).
REM  ~2 hours. Resume-safe.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ABLATE=ts_bars_since_flip,ts_htf_agreement"

cd /d "%ROOT%\engine"

echo ============================================================
echo   ABLATION T10 WFO - FULL (53 weeks)
echo   Removed: ts_bars_since_flip, ts_htf_agreement
echo   Period: 2025-06-23 to 2026-06-29
echo   GATE: >= +80.5R (baseline)
echo   Output: backtest\results\ablation_T10_wfo
echo   ~2 hours. Resume-safe.
echo ============================================================
echo.

"%PY%" run_wfo.py --start 2025-06-23 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir ablation_T10_wfo

if errorlevel 1 (
    echo *** FAILED — resume-safe: re-run to continue. ***
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   WFO DONE.
echo   Results: backtest\results\ablation_T10_wfo\_WFO_SUMMARY.txt
echo   GATE: >= +80.5R to adopt removal.
echo   If PASS: remove ts_bars_since_flip + ts_htf_agreement from
echo     FEATURE_COLS permanently + retrain.
echo   If FAIL: keep features, move to next ablation (T7 OB/SR).
echo ============================================================
pause
