@echo off
setlocal
chcp 65001 >nul
title QGAI - Range filter A/B - SMOKE (30d, ON vs OFF)

REM =====================================================================
REM  Range-phase entry filter A/B (honest 34-feat model already trained).
REM  Measures: does REMOVING the range filter raise or lower R?
REM  Range filter = skip BUY/SELL when in_range_phase==1 (blocks ~63% of
REM  actionable signals in the honest model).
REM
REM  A = range ON  (QGAI_SKIP_RANGE=1) — current live behaviour
REM  B = range OFF (QGAI_SKIP_RANGE=0) — filter REMOVED
REM
REM  SMOKE = 30 days, just verify both run + print R. No config/code change.
REM  CTF stays OFF (QGAI_CTF_FADE=0) to match live. No retrain here.
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
echo   RANGE A/B SMOKE (30d) - honest model
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [A] Range ON (current live)...
set QGAI_SKIP_RANGE=1
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\range_ab_TEST_ON"
if errorlevel 1 goto fail

echo.
echo [B] Range OFF (filter removed)...
set QGAI_SKIP_RANGE=0
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\range_ab_TEST_OFF"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   SMOKE DONE. Compare Total R:
echo     ON : range_ab_TEST_ON\backtest_report.txt
echo     OFF: range_ab_TEST_OFF\backtest_report.txt
echo   If both ran clean -> Run_Range_AB_Backtest.bat (full 1yr)
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED %DATE% %TIME% ***
pause
exit /b 1
