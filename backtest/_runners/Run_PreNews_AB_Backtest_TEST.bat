@echo off
setlocal
chcp 65001 >nul
title QGAI - #2 Pre-news threshold A/B - SMOKE (1 month)

REM =====================================================================
REM  #2 Pre-news threshold override A/B (honest 34-feat model).
REM  Pre-news bars raise the entry threshold by +0.05 (~0.57). This tests
REM  whether that penalty helps or blocks profitable pre-news trades.
REM
REM  A = penalty ON  (QGAI_PRENEWS_PENALTY=0.05) — current behaviour
REM  B = penalty OFF (QGAI_PRENEWS_PENALTY=0)    — no pre-news bar-raise
REM
REM  1 month, no retrain (honest model already trained). CTF + range OFF
REM  (match current live). No config/code change beyond the env toggle.
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
echo   #2 PRE-NEWS A/B SMOKE (1 month) - honest model
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [A] Pre-news penalty ON (+0.05, current)...
set QGAI_PRENEWS_PENALTY=0.05
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\prenews_ab_TEST_ON"
if errorlevel 1 goto fail

echo.
echo [B] Pre-news penalty OFF (0.0)...
set QGAI_PRENEWS_PENALTY=0
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\prenews_ab_TEST_OFF"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   SMOKE DONE. Compare Total R:
echo     ON : prenews_ab_TEST_ON\backtest_report.txt
echo     OFF: prenews_ab_TEST_OFF\backtest_report.txt
echo   OFF >= ON -> pre-news penalty not helping (remove).
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED %DATE% %TIME% ***
pause
exit /b 1
