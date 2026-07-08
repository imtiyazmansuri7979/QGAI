@echo off
title QGAI - FULL-HISTORY 2022-2026 with REGIME-ADAPTIVE TP (live config)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
set "OUT=..\backtest\results\fullhistory_regime"
set "FROM=2022-05-16"
set "TO=2026-06-26"
REM Adopted LIVE config: HTF + CTF-fade + REGIME-ADAPTIVE TP (Rng 2.0/Trn 1.0/Vol 0.8), 0.01 lot.
set "BASE=--equity 10000 --fixed-lot 0.01 --stop-trail htf --ctf-fade --tp-regime"
echo ============================================================
echo   QGAI - FULL HISTORY + REGIME-ADAPTIVE TP  (%FROM% .. %TO%)
echo   2022-2024 = TRUE out-of-sample (model unseen).
echo   This = the ADOPTED live config (regime-TP).
echo   Output: results\fullhistory_regime\
echo ============================================================
echo.
if not exist "%OUT%" mkdir "%OUT%"
"%PY%" backtest_replay.py --from %FROM% --to %TO% %BASE% --out-dir "%OUT%"
echo.
echo ----- build complete signal log -----
"%PY%" build_signal_log.py "%OUT%"
echo.
echo ============================================================
echo   DONE. Tell Claude "regime full history done" to analyze
echo   (BY YEAR: 2022-24 OOS vs 2025-26).
echo ============================================================
pause
