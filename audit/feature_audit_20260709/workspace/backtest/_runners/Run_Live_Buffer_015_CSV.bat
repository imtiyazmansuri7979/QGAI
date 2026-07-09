@echo off
title QGAI - LIVE PARAM BACKTEST CSV (0.15 buffer)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"

REM Live-style replay using current config:
REM - ratchet HTF/forming line from config
REM - regime TP from config/flag
REM - counter-trend fade from config
REM - dynamic 3%% risk sizing (NO fixed-lot)
REM Output includes BOTH trades CSV and signals CSV.
REM Run Run_Live_Buffer_015_CSV_TEST.bat first to catch errors quickly.

set "FROM=2025-06-29"
set "TO=2026-06-29"
set "OUT=C:\QGAI\backtest\results\live_buffer_015"
set "RPT=%OUT%\backtest_report.txt"
set "TRD=%OUT%\backtest_trades_st-htf.csv"
set "SIG=%OUT%\backtest_signals_st-htf.csv"

if not exist "%OUT%" mkdir "%OUT%"
cd /d "C:\QGAI\engine"

echo ============================================================
echo   QGAI - LIVE PARAM BACKTEST CSV
echo ------------------------------------------------------------
echo   Period     : %FROM% -^> %TO%
echo   Buffer     : 0.15%% of ratchet line
echo   Sizing     : LIVE-style dynamic risk 3%%  (no fixed-lot)
echo   TP         : regime-adaptive TP
echo   Trail      : live config default (HTF/forming if enabled)
echo   Output     : %OUT%
echo ------------------------------------------------------------
echo   Files created:
echo     backtest_report.txt
echo     backtest_trades_st-htf.csv
echo     backtest_signals_st-htf.csv
echo ============================================================
echo.

if exist "%RPT%" if exist "%TRD%" if exist "%SIG%" (
    echo [SKIP] Existing completed result found.
    echo        Report : %RPT%
    echo        Trades : %TRD%
    echo        Signal : %SIG%
    echo.
    echo Delete or rename the folder only if you want to force a fresh run.
    echo ============================================================
    pause
    exit /b 0
)

echo [RUN] Missing one or more output files, running replay now...
echo.
"%PY%" backtest_replay.py --from %FROM% --to %TO% --equity 10000 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --out-dir "%OUT%"

echo.
echo ============================================================
echo   DONE.
echo   Report : %RPT%
echo   Trades : %TRD%
echo   Signal : %SIG%
echo ============================================================
pause
