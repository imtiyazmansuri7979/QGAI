@echo off
setlocal
chcp 65001 >nul
title QGAI - TP-Cap Regime Label Diagnostic (cheap, no retrain)

REM =====================================================================
REM  Fable-5's recommended FIRST step (2026-07-13 night) before touching
REM  the flat-vs-regime-adaptive TP-cap training-label bug found today:
REM  relabel_trades.py labels every historical trade Win/Loss using a
REM  FLAT 1.00%% TP cap for all regimes, but the live bridge has used a
REM  REGIME-ADAPTIVE cap (Ranging 2.0 / Trending 1.0 / Volatile 0.8) since
REM  2026-06-27. This script measures HOW MANY historical labels actually
REM  change if you fix that mismatch -- BEFORE committing to a full
REM  relabel + retrain + WFO cycle.
REM
REM  READ-ONLY. No training. Uses the EXISTING production hmm_model.pkl
REM  to classify each historical trade's regime (no HMM refit). No
REM  live/demo impact. Runs in a few minutes (simulates ~2700 trades
REM  twice on M15 OHLC).
REM
REM  DECISION GATE (Fable-5): only proceed to full relabel+retrain+WFO if
REM  TOTAL label flips > ~3%% of trades, OR any single regime's flips
REM  > ~5-7%%. Otherwise the bug is real (fix it eventually for label
REM  correctness) but not worth a full retrain cycle right now.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

echo ============================================================
echo   TP-CAP REGIME LABEL DIAGNOSTIC
echo   %DATE% %TIME%
echo ============================================================

"%PY%" diagnose_tp_cap_regime_labels.py
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   DONE. Results:
echo   backtest\results\tp_cap_regime_diagnostic\tp_cap_diagnostic_report.txt
echo   backtest\results\tp_cap_regime_diagnostic\tp_cap_diagnostic_detail.csv
echo   backtest\results\tp_cap_regime_diagnostic\tp_cap_diagnostic_summary.csv
echo ============================================================
pause
exit /b %RC%
