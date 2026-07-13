@echo off
setlocal
chcp 65001 >nul
title QGAI - Win_Prob Calibration by HTF-Agreement State (cheap, existing data)

REM =====================================================================
REM  Fable-5's Step 1 (2026-07-13 night) for the original live concern:
REM  why did win_prob stay 30-42%% during a clear ~29pt bearish move where
REM  ADX H1/H4 + a separate SMMA trend signal both agreed SELL? The TP-cap
REM  investigation turned out to be a separate tangent (fixed, not the
REM  cause) -- this is the actual next step.
REM
REM  Buckets the 207 real executed trades from the 3-month VolHTFGate WFO
REM  OOS run (backtest\results\volhtfgate_wfo_TEST_A_off\ALL_OOS_trades.csv)
REM  by how many of 4 HTF-direction signals (H1/H4 ADX-DI + H1/H4 SMMA
REM  trend) agree with the direction actually traded, then compares the
REM  model's own PREDICTED win_prob vs the REALIZED win-rate in each
REM  bucket. A real gap in the "aligned_strong" bucket (realized notably
REM  higher than predicted) confirms the model is underconfident exactly
REM  when ADX+SMMA both agree -- before touching any bigger fix.
REM
REM  READ-ONLY. No model inference, no retrain, no live/demo impact. Uses
REM  data already on disk. Runs in seconds.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

echo ============================================================
echo   WIN_PROB CALIBRATION BY HTF-AGREEMENT STATE
echo   %DATE% %TIME%
echo ============================================================

"%PY%" diagnose_win_prob_calibration.py
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   DONE. Results:
echo   backtest\results\win_prob_calibration_diagnostic\calibration_report.txt
echo   backtest\results\win_prob_calibration_diagnostic\calibration_detail.csv
echo   backtest\results\win_prob_calibration_diagnostic\calibration_summary.csv
echo ============================================================
pause
exit /b %RC%
