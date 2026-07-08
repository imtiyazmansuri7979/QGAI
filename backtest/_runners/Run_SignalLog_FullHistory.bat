@echo off
title QGAI - Build COMPLETE signal log 2022-2026 (every candle @0.01 lot)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
set "OUT=..\backtest\results\signal_log_full"
set "FROM=2022-05-16"
set "TO=2026-06-26"
REM Live-faithful config: HTF flip + CTF-fade, price TP cap 1.0 (NOT --tp-equity), 0.01 lot.
set "BASE=--equity 10000 --fixed-lot 0.01 --stop-trail htf --ctf-fade --tp-cap 1.0"
echo ============================================================
echo   QGAI - COMPLETE SIGNAL LOG  (%FROM% .. %TO%)
echo   Step 1: backtest every M15 candle (BUY/SELL/SKIP + outcome)
echo   Step 2: build dashboard-ready signals_complete.csv @0.01 lot
echo   2022-2024 = current model on UNSEEN data (honest backtest signals).
echo   Output: results\signal_log_full\signals_complete.csv
echo ============================================================
echo.
if not exist "%OUT%" mkdir "%OUT%"
echo ----- [1/2] backtest replay (every candle) -----------------
"%PY%" backtest_replay.py --from %FROM% --to %TO% %BASE% --out-dir "%OUT%"
echo.
echo ----- [2/2] build complete signal log ----------------------
"%PY%" build_signal_log.py "%OUT%"
echo.
echo ============================================================
echo   DONE. Open: results\signal_log_full\signals_complete.csv
echo   Every candle 2022-2026: signal / WIN-LOSS / $move / %%move @0.01 lot.
echo   Tell Claude "signal log done" to view / put on dashboard.
echo ============================================================
pause
