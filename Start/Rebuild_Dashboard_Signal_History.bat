@echo off
setlocal
chcp 65001 >nul
title QGAI - Rebuild Dashboard Signal History (display-only)

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "OUT=%ROOT%\backtest\results\signal_log_full"

cd /d "%ROOT%\engine"

echo ============================================================
echo   QGAI - REBUILD DASHBOARD SIGNAL HISTORY
echo ------------------------------------------------------------
echo   DISPLAY-ONLY / IN-SAMPLE HISTORY BUILDER
echo.
echo   This is NOT an OOS/profit-proof backtest.
echo   It intentionally uses --allow-in-sample so the dashboard can
echo   restore the full historical Signal Log after a fresh git pull.
echo.
echo   Output:
echo     %OUT%
echo   Final dashboard file:
echo     %ROOT%\engine\logs\signals_complete.csv
echo ============================================================

if not exist "%OUT%" mkdir "%OUT%"

"%PY%" backtest_replay.py --from 2022-05-16 --to 2026-06-26 --equity 10000 --fixed-lot 0.01 --stop-trail htf --ctf-fade --tp-cap 1.0 --allow-in-sample --out-dir "%OUT%"
if errorlevel 1 goto fail

"%PY%" build_signal_log.py "%OUT%"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   DONE
echo   Dashboard Signal Log history rebuilt.
echo ============================================================
pause
exit /b 0

:fail
echo.
echo ============================================================
echo   FAILED
echo   Check the error above. Existing signals_complete.csv was preserved
echo   unless build_signal_log.py had a valid backtest_signals file.
echo ============================================================
pause
exit /b 1
