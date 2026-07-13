@echo off
setlocal
chcp 65001 >nul
title QGAI - Post-Cap Continuation Audit (TPCAP money-left-on-table check)

REM =====================================================================
REM  Fable-5's 4th opinion (2026-07-13, smart Exit-AI vs rule-based exits):
REM  before building any exit-AI model, first MEASURE whether the hard
REM  TP-cap is actually leaving money on the table. For every trade that
REM  exited via TPCAP in the existing feature-sweep baseline run, this
REM  replays forward using the SAME H1-line trail + HTF-flip exit already
REM  live for non-capped trades, and reports how much extra profit (or
REM  giveback) would have happened had the cap not force-closed the trade.
REM
REM  READ-ONLY. No model, no retrain, no live/demo impact. Pure pandas +
REM  OHLC replay over an EXISTING trades CSV (already on disk from the
REM  active_baseline feature-sweep run). Runs in seconds.
REM
REM  Decides the next step: if extra R is clearly positive and giveback
REM  is small -> worth trying partial-exit-at-cap / trail-tighten-at-cap
REM  (Fable's main recommendation) + WFO A/B. If giveback is large ->
REM  the cap is doing its job, retire the capture% target instead.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

set "TRADES_CSV=%ROOT%\backtest\results\feature_sweep\active_baseline\backtest_trades_st-htf.csv"

if not exist "%TRADES_CSV%" (
    echo ============================================================
    echo   ERROR: trades CSV not found:
    echo   %TRADES_CSV%
    echo   Run Run_FeatureSweep_TEST.bat or Run_FeatureSweep_PriorityBatch.bat
    echo   at least once first to produce the baseline trades file.
    echo ============================================================
    pause
    exit /b 1
)

echo ============================================================
echo   POST-CAP CONTINUATION AUDIT
echo   Source: %TRADES_CSV%
echo   %DATE% %TIME%
echo ============================================================

"%PY%" analyze_post_cap_continuation.py --trades-csv "%TRADES_CSV%" --max-bars 384
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   DONE. Results:
echo   backtest\results\feature_sweep\active_baseline\post_cap_audit\post_cap_audit_report.txt
echo   backtest\results\feature_sweep\active_baseline\post_cap_audit\post_cap_audit_detail.csv
echo   backtest\results\feature_sweep\active_baseline\post_cap_audit\post_cap_audit_summary.csv
echo ============================================================
pause
exit /b %RC%
