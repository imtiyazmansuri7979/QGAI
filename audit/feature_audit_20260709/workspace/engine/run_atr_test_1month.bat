@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title QGAI - ATR Test (1 month, quick)
cls

cd /d "%~dp0"

if not exist atr_results mkdir atr_results

echo ============================================================
echo   QGAI ATR vs No-ATR - 1 MONTH QUICK TEST (2026-03)
echo   buffer 0.06%%, TP cap 3%%, ratchet ON
echo ============================================================
echo.

REM Test 1: WITH ATR (current)
if exist "atr_results\withATR_mar.txt" (
    echo [1/2]  WITH ATR - already done, SKIP
) else (
    echo [1/2]  WITH ATR - running...
    python backtest_replay.py --from 2026-03-01 --to 2026-03-31 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.06 --tp-cap 3 > "atr_results\withATR_mar.txt.tmp" 2>&1
    if errorlevel 1 (
        echo    ERROR
    ) else (
        ren "atr_results\withATR_mar.txt.tmp" "withATR_mar.txt"
        echo    [saved] withATR_mar.txt
    )
)

REM Test 2: NO ATR (skip-counter-trend)
if exist "atr_results\noATR_mar.txt" (
    echo [2/2]  NO ATR - already done, SKIP
) else (
    echo [2/2]  NO ATR - running...
    python backtest_replay.py --from 2026-03-01 --to 2026-03-31 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.06 --tp-cap 3 --skip-counter-trend > "atr_results\noATR_mar.txt.tmp" 2>&1
    if errorlevel 1 (
        echo    ERROR
    ) else (
        ren "atr_results\noATR_mar.txt.tmp" "noATR_mar.txt"
        echo    [saved] noATR_mar.txt
    )
)

echo.
echo   Combining...
set OUT=atr_results\_COMPARE_mar.txt
echo QGAI ATR vs No-ATR - 1 MONTH (2026-03) > %OUT%
echo. >> %OUT%
echo ##### WITH ATR (current) ##### >> %OUT%
if exist "atr_results\withATR_mar.txt" type "atr_results\withATR_mar.txt" >> %OUT%
echo. >> %OUT%
echo ##### NO ATR (skip-counter-trend) ##### >> %OUT%
if exist "atr_results\noATR_mar.txt" type "atr_results\noATR_mar.txt" >> %OUT%

echo   DONE! %OUT%
notepad %OUT%
pause
