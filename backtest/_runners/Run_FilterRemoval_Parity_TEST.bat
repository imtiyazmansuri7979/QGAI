@echo off
setlocal
chcp 65001 >nul
title QGAI - Filter-removal PARITY smoke (1 month)

REM =====================================================================
REM  BUG-CHECK / PARITY smoke after deleting the range + #2 pre-news +
REM  #4 early-discount FILTER CODE (2026-07-12).
REM
REM  These filters were already functionally OFF, so removing the code must
REM  NOT change results. Expected = IDENTICAL to the earlier range-OFF run:
REM     +8.9R / 63 trades / WR 60.3% / PF 1.95   (range_ab_TEST_OFF)
REM
REM  Any difference = a bug introduced by the code removal -> investigate.
REM  No retrain (honest 34-feat model already trained).
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_CTF_FADE=0"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT=C:\QGAI\backtest\results\filter_removal_parity_TEST"

cd /d "%ROOT%\engine"

echo ============================================================
echo   FILTER-REMOVAL PARITY smoke (1 month)
echo   Expect IDENTICAL to range_ab_TEST_OFF: +8.9R / 63 tr
echo   %DATE% %TIME%
echo ============================================================

"%PY%" "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "%OUT%"
if errorlevel 1 (
    echo *** FAILED - check error above ***
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   DONE. Check %OUT%\backtest_report.txt
echo   MUST equal +8.9R / 63 tr. If different -> code-removal bug.
echo ============================================================
pause
