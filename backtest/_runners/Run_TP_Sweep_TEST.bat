@echo off
title QGAI - TP-cap sweep TEST (short) - verify pipeline
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
set "OUT=..\backtest\results\backtests"
REM --- SHORT window to confirm the sweep runs end-to-end (fast) ---
set "FROM=2026-05-26"
set "TO=2026-06-12"
set "BASE=--equity 10000 --fixed-lot 0.01 --stop-trail htf --ctf-fade"
echo ============================================================
echo   QGAI - TP-CAP SWEEP **TEST** (short %FROM% .. %TO%)
echo   $10,000 capital, 0.01 lot, HTF + CTF ON. 10 TP variants.
echo   Smoke-test before the full run. Saves to tptest_*  (resumable)
echo ============================================================
echo.
for %%T in (0.5 0.6 0.7 0.8 0.9 1 1.1 1.2 1.3 1.4 1.5 2 3) do (
  if exist "%OUT%\tptest_%%T\backtest_report.txt" (
    echo   [SKIP] tptest_%%T already done
  ) else (
    echo ----- TEST TP = %%T %% -------------------------------------
    "%PY%" backtest_replay.py --from %FROM% --to %TO% %BASE% --tp-cap %%T --out-dir "%OUT%\tptest_%%T"
  )
)
echo.
echo ============================================================
echo   TEST done. Check backtest\results\backtests\tptest_*\
echo   backtest_report.txt all exist with NO errors.
echo   If OK -^> run Run_TP_Sweep.bat for the full period.
echo ============================================================
pause
