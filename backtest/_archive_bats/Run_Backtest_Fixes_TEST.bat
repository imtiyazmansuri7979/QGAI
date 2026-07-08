@echo off
title QGAI - TEST run (short) - verify the fixes pipeline works
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
REM --- new backtests saved SEPARATELY under backtest\results\backtests\ ---
set "OUT=..\backtest\results\backtests"
REM --- SHORT window just to confirm everything runs end-to-end (fast) ---
set "FROM=2026-05-26"
set "TO=2026-06-12"
echo ============================================================
echo   QGAI - TEST RUN (short %FROM% .. %TO%)
echo   Saves to: backtest\results\backtests\test_*  (separate
echo   from WFO, which stays in backtest\results\wfo_*).
echo ============================================================
echo.
echo ----- 1) BASELINE -------------------------------------------
"%PY%" backtest_replay.py --from %FROM% --to %TO% --fixed-lot 0.01 --out-dir "%OUT%\test_baseline"
echo.
echo ----- 2) + CTF-FADE -----------------------------------------
"%PY%" backtest_replay.py --from %FROM% --to %TO% --fixed-lot 0.01 --ctf-fade --out-dir "%OUT%\test_ctf"
echo.
echo ----- 3) + HTF FLIP -----------------------------------------
"%PY%" backtest_replay.py --from %FROM% --to %TO% --fixed-lot 0.01 --stop-trail htf --out-dir "%OUT%\test_htf"
echo.
echo ----- 4) + BOTH ---------------------------------------------
"%PY%" backtest_replay.py --from %FROM% --to %TO% --fixed-lot 0.01 --stop-trail htf --ctf-fade --out-dir "%OUT%\test_both"
echo.
echo ============================================================
echo   TEST done. Reports in backtest\results\backtests\test_*\
echo   Each: backtest_report.txt + backtest_trades*.csv +
echo         backtest_signals*.csv (with blocked_by column).
echo   If all 4 ran with NO errors -^> run Run_Backtest_Fixes.bat
echo ============================================================
pause
