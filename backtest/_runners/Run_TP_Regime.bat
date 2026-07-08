@echo off
title QGAI - REGIME-ADAPTIVE TP backtest (real model)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
set "OUT=..\backtest\results\backtests\tp_regime"
set "FROM=2025-09-01"
set "TO=2026-06-12"
REM --- SAME settings as Run_TP_Sweep.bat (10k, 0.01 fixed lot, HTF flip + CTF-fade)
REM     so it is apples-to-apples vs the tp_* sweep. Only difference: --tp-regime
REM     picks the TP cap by HMM state at entry (Ranging 2.0 / Trending 1.0 / Volatile 0.8).
set "BASE=--equity 10000 --fixed-lot 0.01 --stop-trail htf --ctf-fade"
echo ============================================================
echo   QGAI - REGIME-ADAPTIVE TP   (%FROM% .. %TO%)
echo   TP cap switches per HMM state at entry:
echo     Ranging  -^> 2.0%%   Trending -^> 1.0%%   Volatile -^> 0.8%%
echo   Compare vs global TP=1.0 (results\backtests\tp_1).
echo   Output: results\backtests\tp_regime\backtest_report.txt
echo ============================================================
echo.
if not exist "%OUT%" mkdir "%OUT%"
"%PY%" backtest_replay.py --from %FROM% --to %TO% %BASE% --tp-regime --out-dir "%OUT%"
echo.
echo ============================================================
echo   DONE. Open: results\backtests\tp_regime\backtest_report.txt
echo   Compare Total R / PF / Max DD / BY REGIME vs tp_1 (global 1.0).
echo   Then tell Claude "regime TP done" to analyze.
echo ============================================================
pause
