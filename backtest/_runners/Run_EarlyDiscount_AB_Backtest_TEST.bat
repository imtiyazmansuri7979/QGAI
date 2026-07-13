@echo off
setlocal
chcp 65001 >nul
title QGAI - #4 Early-entry discount A/B - SMOKE (1 month)

REM =====================================================================
REM  #4 Early-entry threshold DISCOUNT A/B (honest 34-feat model).
REM  Within 3 bars of a fresh SMMA flip + HTF agreement>=2 + non-Ranging
REM  + state_prob>=0.60 -> LOWER the entry threshold by delta (0.05) so
REM  marginal-confident signals fire at the START of a trend.
REM  ADDS trades only, never blocks -> prime-directive safe.
REM
REM  A = discount OFF (QGAI_EARLY_DISCOUNT=0) — current behaviour
REM  B = discount ON  (QGAI_EARLY_DISCOUNT=1) — adds early-trend entries
REM
REM  1 month, no retrain. CTF + range OFF (match current live).
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_CTF_FADE=0"
set "QGAI_SKIP_RANGE=0"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "BASE=--from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"

cd /d "%ROOT%\engine"

echo ============================================================
echo   #4 EARLY-DISCOUNT A/B SMOKE (1 month) - honest model
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [A] Early-discount OFF (current)...
set QGAI_EARLY_DISCOUNT=0
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\earlydisc_ab_TEST_OFF"
if errorlevel 1 goto fail

echo.
echo [B] Early-discount ON (adds early-trend entries)...
set QGAI_EARLY_DISCOUNT=1
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\earlydisc_ab_TEST_ON"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   SMOKE DONE. Compare Total R:
echo     OFF: earlydisc_ab_TEST_OFF\backtest_report.txt
echo     ON : earlydisc_ab_TEST_ON\backtest_report.txt
echo   ON >= OFF -> early-discount adds profitable trades (adopt).
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED %DATE% %TIME% ***
pause
exit /b 1
