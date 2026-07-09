@echo off
title QGAI - REGIME-ADAPTIVE TP **TEST** (short, smoke-test)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
set "OUT=..\backtest\results\backtests\tp_regime_test"
REM --- SHORT window to confirm the regime-adaptive TP runs end-to-end (fast) ---
set "FROM=2026-05-26"
set "TO=2026-06-12"
REM Same settings as Run_TP_Sweep_TEST.bat (10k, 0.01 lot, HTF flip + CTF-fade),
REM only --tp-regime added (TP cap by HMM state: Rng 2.0 / Trn 1.0 / Vol 0.8).
set "BASE=--equity 10000 --fixed-lot 0.01 --stop-trail htf --ctf-fade"
echo ============================================================
echo   QGAI - REGIME-ADAPTIVE TP **TEST**  (short %FROM% .. %TO%)
echo   Smoke-test before the full run. TP switches per HMM state.
echo   Output: results\backtests\tp_regime_test\backtest_report.txt
echo ============================================================
echo.
if not exist "%OUT%" mkdir "%OUT%"
"%PY%" backtest_replay.py --from %FROM% --to %TO% %BASE% --tp-regime --out-dir "%OUT%"
echo.
echo ============================================================
echo   TEST done, no errors? -^> run the FULL: Run_TP_Regime.bat
echo   (Look for the "REGIME-ADAPTIVE TP ON" line near the top.)
echo ============================================================
pause
