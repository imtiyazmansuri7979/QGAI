@echo off
setlocal
chcp 65001 >nul
title QGAI - HTF-Alignment Skip-Rate Diagnostic (cheap, existing data + recomputed trend)

REM =====================================================================
REM  Imtiyaz's follow-up (2026-07-14) to Run_WinProbCalibration_TEST.bat:
REM  "most of the aligned_strong bars are probably SKIPPED, not traded --
REM  that is the real question."
REM
REM  The win_prob calibration diagnostic only looked at 207 EXECUTED trades
REM  -- it can't see skipped bars. This tool reads the SAME 3-month WFO OOS
REM  run's per-bar signal log (backtest\results\volhtfgate_wfo_TEST_A_off\
REM  ALL_OOS_signals.csv, every bar incl. SKIP) and recomputes the H1/H4
REM  SMMA trend (frozen indicator math, same as everywhere else in the
REM  codebase -- NOT a model call, NOT a retrain) to bucket EVERY bar by
REM  HTF-signal agreement (H1/H4 ADX-DI + H1/H4 SMMA trend), then reports
REM  what fraction of each bucket was actually traded vs skipped.
REM
REM  READ-ONLY. No model inference, no retrain, no live/demo impact.
REM  Runs in under a minute (recomputes trend once over the full OHLC file,
REM  then a fast per-bar lookup for ~6,575 bars).
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

echo ============================================================
echo   HTF-ALIGNMENT SKIP-RATE DIAGNOSTIC
echo   %DATE% %TIME%
echo ============================================================

"%PY%" diagnose_htf_alignment_skip_rate.py
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   DONE. Results:
echo   backtest\results\htf_alignment_skip_rate_diagnostic\htf_alignment_skip_rate_report.txt
echo   backtest\results\htf_alignment_skip_rate_diagnostic\htf_alignment_skip_rate_summary.csv
echo   backtest\results\htf_alignment_skip_rate_diagnostic\htf_alignment_skip_rate_detail.csv
echo ============================================================
pause
exit /b %RC%
