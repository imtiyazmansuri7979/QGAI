@echo off
title QGAI - TEST live param CSV backtest (0.15 buffer)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"

REM Smoke test before the full 1-year CSV backtest.
REM Same live-style parameters as Run_Live_Buffer_015_CSV.bat,
REM but short date range so errors are caught quickly.

set "FROM=2026-06-01"
set "TO=2026-06-08"
set "OUT=C:\QGAI\backtest\results\live_buffer_015_TEST"
set "RPT=%OUT%\backtest_report.txt"
set "TRD=%OUT%\backtest_trades_st-htf.csv"
set "SIG=%OUT%\backtest_signals_st-htf.csv"

if not exist "%OUT%" mkdir "%OUT%"
cd /d "C:\QGAI\engine"

echo ============================================================
echo   QGAI - TEST RUN: LIVE PARAM BACKTEST CSV
echo ------------------------------------------------------------
echo   Period     : %FROM% -^> %TO%
echo   Buffer     : 0.15%% of ratchet line
echo   Sizing     : LIVE-style dynamic risk 3%%  (no fixed-lot)
echo   Output     : %OUT%
echo ============================================================
echo.

"%PY%" backtest_replay.py --from %FROM% --to %TO% --equity 10000 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --out-dir "%OUT%"

echo.
echo ============================================================
if exist "%RPT%" if exist "%TRD%" if exist "%SIG%" (
    echo   TEST OK - all output files created.
    echo   Report : %RPT%
    echo   Trades : %TRD%
    echo   Signal : %SIG%
) else (
    echo   TEST FAILED - one or more output files missing.
    echo   Check console error above.
)
echo ============================================================
pause
