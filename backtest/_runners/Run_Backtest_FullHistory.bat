@echo off
title QGAI - TOTAL DATASET backtest (full 4-year history, real model)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
REM === FULL OHLC/ADX range: 2022-05-16 -> 2026-06-26 (97,235 M15 bars) ===
REM Model trained only on Dec-2024+ => 2022-05..2024-11 is TRUE out-of-sample.
REM Same settings as the TP sweep ($10k, 0.01 fixed-lot, HTF flip + CTF-fade)
REM so it is comparable. Runs TWO variants for comparison. Resumable.
set "FROM=2022-05-16"
set "TO=2026-06-26"
set "BASE=--equity 10000 --fixed-lot 0.01 --stop-trail htf --ctf-fade"
set "OUT=..\backtest\results\fullhistory"
echo ============================================================
echo   QGAI - TOTAL DATASET BACKTEST   (%FROM% .. %TO%)
echo   ~4.1 years. 2022-05..2024-11 = honest OUT-OF-SAMPLE.
echo   Two runs: (1) global TP=1.0   (2) regime-adaptive TP
echo ============================================================
echo.

echo ----- [1/2] GLOBAL TP = 1.0 -------------------------------
if exist "%OUT%\global_tp1\backtest_report.txt" (
  echo   [SKIP] already done
) else (
  if not exist "%OUT%\global_tp1" mkdir "%OUT%\global_tp1"
  "%PY%" backtest_replay.py --from %FROM% --to %TO% %BASE% --tp-cap 1.0 --out-dir "%OUT%\global_tp1"
)
echo.

echo ----- [2/2] REGIME-ADAPTIVE TP (Rng 2.0 / Trn 1.0 / Vol 0.8) -----
if exist "%OUT%\regime_adaptive\backtest_report.txt" (
  echo   [SKIP] already done
) else (
  if not exist "%OUT%\regime_adaptive" mkdir "%OUT%\regime_adaptive"
  "%PY%" backtest_replay.py --from %FROM% --to %TO% %BASE% --tp-regime --out-dir "%OUT%\regime_adaptive"
)
echo.
echo ============================================================
echo   DONE. Reports:
echo     results\fullhistory\global_tp1\backtest_report.txt
echo     results\fullhistory\regime_adaptive\backtest_report.txt
echo   Check BY MONTH: 2022-24 rows = honest OOS. Tell Claude
echo   "full history done" to analyze.
echo ============================================================
pause
