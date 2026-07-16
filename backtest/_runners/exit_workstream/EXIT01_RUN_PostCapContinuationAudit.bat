@echo off
setlocal
chcp 65001 >nul
title QGAI - EXIT01 Post-Cap Continuation Audit (TPCAP money-left-on-table check)

REM =====================================================================
REM  Registry ID: EXIT01  (exit-model work stream, step 1 of 5 -- see
REM  docs\TASKS.md "TOP PRIORITY -- Exit Model / Exit-AI work stream")
REM
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
REM  active_baseline feature-sweep run). Runs in seconds. Same ID (EXIT01)
REM  appears in this filename and the result folder name, matching the
REM  feature_sweep_67 registry convention (see that folder's README.md).
REM
REM  Decides the next step: if extra R is clearly positive and giveback
REM  is small -> worth trying partial-exit-at-cap / trail-tighten-at-cap
REM  (Fable's main recommendation, EXIT02) + WFO A/B. If giveback is large
REM  -> the cap is doing its job, retire the capture% target instead.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

set "TRADES_CSV=%ROOT%\backtest\results\feature_sweep\active_baseline\backtest_trades_st-htf.csv"
set "OUT_DIR=%ROOT%\backtest\results\exit_workstream\EXIT01_post_cap_continuation_audit"

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
echo   EXIT01 - POST-CAP CONTINUATION AUDIT
echo   Source: %TRADES_CSV%
echo   Output: %OUT_DIR%
echo   %DATE% %TIME%
echo ============================================================

"%PY%" analyze_post_cap_continuation.py --trades-csv "%TRADES_CSV%" --max-bars 384 --out-dir "%OUT_DIR%"
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   DONE. Results (registry ID EXIT01):
echo   %OUT_DIR%\post_cap_audit_report.txt
echo   %OUT_DIR%\post_cap_audit_detail.csv
echo   %OUT_DIR%\post_cap_audit_summary.csv
echo ============================================================
pause
exit /b %RC%
