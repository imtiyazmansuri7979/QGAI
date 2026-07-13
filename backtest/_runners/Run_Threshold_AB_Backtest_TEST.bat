@echo off
setlocal
chcp 65001 >nul
title QGAI - #1 min_win_prob threshold A/B - SMOKE (1 month)

REM =====================================================================
REM  #1 ML confidence threshold A/B (honest 34-feat model).
REM  Lower the entry bar -> take more trades, trust the model more
REM  ("model over hard filters"). Regime thresholds today:
REM    Ranging 0.48 / Trending 0.45 / Volatile 0.42.
REM  Env QGAI_THRESH_OFFSET subtracts a uniform amount from all of them.
REM
REM  A = offset 0.00 (current bars)
REM  B = offset 0.05 (Ranging 0.43 / Trending 0.40 / Volatile 0.37)
REM
REM  1 month, no retrain. CTF + range already removed (current live).
REM  ON >= current AND WR stays healthy -> lower the bar (adopt).
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_CTF_FADE=0"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "BASE=--from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"

cd /d "%ROOT%\engine"

echo ============================================================
echo   #1 THRESHOLD A/B SMOKE (1 month) - honest model
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [A] offset 0.00 (current threshold)...
set QGAI_THRESH_OFFSET=0
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\thresh_ab_TEST_off000"
if errorlevel 1 goto fail

echo.
echo [B] offset 0.05 (lower bar, more trades)...
set QGAI_THRESH_OFFSET=0.05
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\thresh_ab_TEST_off005"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   SMOKE DONE. Compare Total R + Win rate + trade count:
echo     A off0.00: thresh_ab_TEST_off000\backtest_report.txt
echo     B off0.05: thresh_ab_TEST_off005\backtest_report.txt
echo   B >= A on Total R AND WR still healthy -> lower the bar.
echo   (If more trades but R/WR drop -> keep current bar.)
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED %DATE% %TIME% ***
pause
exit /b 1
