@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title QGAI - ATR vs No-ATR Test
cls

cd /d "%~dp0"

if not exist atr_results mkdir atr_results

echo ============================================================
echo   QGAI ATR vs No-ATR (skip-counter-trend) TEST
echo   buffer 0.06%%, TP cap 3%%, ratchet ON, risk 3%%
echo ============================================================
echo.

REM Test 1: WITH ATR (current)
if exist "atr_results\withATR.txt" (
    echo [1/2]  WITH ATR - already done, SKIP
) else (
    echo [1/2]  WITH ATR - running...
    python backtest_replay.py --from 2025-06-01 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.06 --tp-cap 3 > "atr_results\withATR.txt.tmp" 2>&1
    if errorlevel 1 (
        echo    ERROR - see withATR.txt.tmp
    ) else (
        ren "atr_results\withATR.txt.tmp" "withATR.txt"
        echo    [saved] withATR.txt
    )
)

REM Test 2: NO ATR (skip-counter-trend)
if exist "atr_results\noATR.txt" (
    echo [2/2]  NO ATR - already done, SKIP
) else (
    echo [2/2]  NO ATR - running...
    python backtest_replay.py --from 2025-06-01 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.06 --tp-cap 3 --skip-counter-trend > "atr_results\noATR.txt.tmp" 2>&1
    if errorlevel 1 (
        echo    ERROR - see noATR.txt.tmp
    ) else (
        ren "atr_results\noATR.txt.tmp" "noATR.txt"
        echo    [saved] noATR.txt
    )
)

echo.
echo ============================================================
echo   Combining...
set OUT=atr_results\_COMPARE.txt
echo QGAI ATR vs No-ATR COMPARISON > %OUT%
echo. >> %OUT%
echo ##### WITH ATR (current) ##### >> %OUT%
if exist "atr_results\withATR.txt" type "atr_results\withATR.txt" >> %OUT%
echo. >> %OUT%
echo ##### NO ATR (skip-counter-trend) ##### >> %OUT%
if exist "atr_results\noATR.txt" type "atr_results\noATR.txt" >> %OUT%

echo   DONE! Combined: %OUT%
notepad %OUT%
pause
