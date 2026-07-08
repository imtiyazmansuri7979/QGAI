@echo off
title QGAI - Backtest the two fixes (HTF flip + counter-trend-fade)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
REM --- new backtests saved SEPARATELY under backtest\results\backtests\ ---
set "OUT=..\backtest\results\backtests"
set "FROM=2025-09-01"
set "TO=2026-06-12"
echo ============================================================
echo   QGAI - BACKTEST THE FIXES   (%FROM%  ..  %TO%)
echo   Saves to: backtest\results\backtests\fix_*  (separate from
echo   WFO, which lives in backtest\results\wfo_*).
echo   RESUMABLE: a run that already has backtest_report.txt is
echo   SKIPPED. Delete its fix_* folder to force a re-run.
echo     1 BASELINE   2 +CTF-FADE   3 +HTF flip   4 +BOTH
echo ============================================================
echo.

echo ----- 1) BASELINE -------------------------------------------
if exist "%OUT%\fix_baseline\backtest_report.txt" (
  echo   [SKIP] already done - backtests\fix_baseline
) else (
  "%PY%" backtest_replay.py --from %FROM% --to %TO% --fixed-lot 0.01 --out-dir "%OUT%\fix_baseline"
)
echo.
echo ----- 2) + CTF-FADE -----------------------------------------
if exist "%OUT%\fix_ctf\backtest_report.txt" (
  echo   [SKIP] already done - backtests\fix_ctf
) else (
  "%PY%" backtest_replay.py --from %FROM% --to %TO% --fixed-lot 0.01 --ctf-fade --out-dir "%OUT%\fix_ctf"
)
echo.
echo ----- 3) + HTF FLIP -----------------------------------------
if exist "%OUT%\fix_htf\backtest_report.txt" (
  echo   [SKIP] already done - backtests\fix_htf
) else (
  "%PY%" backtest_replay.py --from %FROM% --to %TO% --fixed-lot 0.01 --stop-trail htf --out-dir "%OUT%\fix_htf"
)
echo.
echo ----- 4) + BOTH (HTF + CTF) ---------------------------------
if exist "%OUT%\fix_both\backtest_report.txt" (
  echo   [SKIP] already done - backtests\fix_both
) else (
  "%PY%" backtest_replay.py --from %FROM% --to %TO% --fixed-lot 0.01 --stop-trail htf --ctf-fade --out-dir "%OUT%\fix_both"
)
echo.
echo ============================================================
echo   Done. Compare the 4 reports in:
echo     backtest\results\backtests\fix_baseline\backtest_report.txt
echo     backtest\results\backtests\fix_ctf\backtest_report.txt
echo     backtest\results\backtests\fix_htf\backtest_report.txt
echo     backtest\results\backtests\fix_both\backtest_report.txt
echo   Higher Total R + PF = better. If BOTH wins, enable in config:
echo     ratchet_htf_sl=True, ratchet_htf_flip=True, skip_counter_trend_fade=True
echo   Then DEMO forward-test before live.
echo ============================================================
pause
