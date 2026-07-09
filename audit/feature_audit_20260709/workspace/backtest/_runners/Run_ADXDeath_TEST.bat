@echo off
setlocal
chcp 65001 >nul
title QGAI - ADX-Death EXIT - 2-week SMOKE TEST

REM =====================================================================
REM  ADX-Death exit rule - quick 2-week smoke test.
REM  Verifies: no crashes, ADX_DEATH exit_reason appears in trades CSV,
REM  output files written. ~2-3 min.
REM
REM  Default params: K=3, N=3, min_r=0.5
REM  Flag: QGAI_ADX_DEATH=1
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT=C:\QGAI\backtest\results\adx_death_test"

set QGAI_ADX_DEATH=1
set QGAI_ADX_DEATH_K=3
set QGAI_ADX_DEATH_N=3
set QGAI_ADX_DEATH_MIN_R=0.5

if not exist "%OUT%" mkdir "%OUT%"
cd /d "%ROOT%\engine"

echo ============================================================
echo ADX-DEATH SMOKE TEST  %DATE% %TIME%
echo   K=%QGAI_ADX_DEATH_K%  N=%QGAI_ADX_DEATH_N%  min_r=%QGAI_ADX_DEATH_MIN_R%
echo   Period: 2 weeks only (2026-01-05 to 2026-01-19)
echo ============================================================

"%PY%" "%SCRIPT%" --from 2026-01-05 --to 2026-01-19 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --out-dir "%OUT%"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo SMOKE TEST DONE %DATE% %TIME%
echo   Check: %OUT%\backtest_report.txt
echo   Verify ADX_DEATH exits appear in backtest_trades*.csv
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED - check error above. ***
pause
exit /b 1
