@echo off
setlocal
chcp 65001 >nul
title QGAI - Range filter A/B - FULL 1yr (ON vs OFF, honest model)

REM =====================================================================
REM  Range-phase entry filter A/B on the honest 34-feat model.
REM  Filter is now REMOVED in config (skip_range_phase_entry=False, 07-12).
REM  This bat MEASURES the profit impact of that removal (rule: judge by R).
REM
REM  A = range ON  (QGAI_SKIP_RANGE=1) — old live behaviour
REM  B = range OFF (QGAI_SKIP_RANGE=0) — filter removed (new default)
REM
REM  Decision:
REM    OFF R >= ON R  -> removal confirmed (keep it removed).
REM    OFF R <  ON R by a lot -> reconsider / revert (config back to True).
REM
REM  Prior A/B (2026-07-03, IN-SAMPLE + leaky model): ON=+350.3R / OFF=+340.0R
REM  (+10R for ON). This honest OOS-style check supersedes that.
REM  CTF stays OFF. No retrain (honest model already trained). Run TEST first.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_CTF_FADE=0"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "BASE=--from 2025-06-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"

cd /d "%ROOT%\engine"

echo ============================================================
echo   RANGE A/B FULL 1yr - honest model
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [A] Range ON (old live)...
set QGAI_SKIP_RANGE=1
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\range_ab_FULL_ON"
if errorlevel 1 goto fail

echo.
echo [B] Range OFF (removed - new default)...
set QGAI_SKIP_RANGE=0
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\range_ab_FULL_OFF"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   DONE %DATE% %TIME%  Compare Total R:
echo     ON : range_ab_FULL_ON\backtest_report.txt
echo     OFF: range_ab_FULL_OFF\backtest_report.txt
echo   OFF >= ON  -> keep removed.  OFF much lower -> reconsider revert.
echo   (Backtest = direction; WFO is the honest gate if you want to confirm.)
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED %DATE% %TIME% ***
pause
exit /b 1
