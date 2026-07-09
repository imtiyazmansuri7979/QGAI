@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title QGAI - Buffer x EquityTP Sweep (FULL YEAR)
cls

cd /d "%~dp0"

if not exist sweep_year mkdir sweep_year

echo ============================================================
echo   QGAI FULL-YEAR SWEEP  (2025-06-12 to 2026-06-12)
echo   6 buffers x 2 TP (3%%, 4%%) = 12 tests
echo   ATR-free (skip-counter-trend), 3%% risk
echo   ~12 hours. Resume-able (skips done combos).
echo ============================================================
echo.

set /a N=0
set /a N+=1
if exist "sweep_year\buf006_tp3.txt" (
    echo [!N!/12]  buf 0.06%% TP 3%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.06%% TP 3%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.06 --tp-equity-pct 3 --skip-counter-trend > "sweep_year\buf006_tp3.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf006_tp3.txt.tmp" "buf006_tp3.txt" & echo    [saved] buf006_tp3.txt )
)
set /a N+=1
if exist "sweep_year\buf006_tp4.txt" (
    echo [!N!/12]  buf 0.06%% TP 4%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.06%% TP 4%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.06 --tp-equity-pct 4 --skip-counter-trend > "sweep_year\buf006_tp4.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf006_tp4.txt.tmp" "buf006_tp4.txt" & echo    [saved] buf006_tp4.txt )
)
set /a N+=1
if exist "sweep_year\buf009_tp3.txt" (
    echo [!N!/12]  buf 0.09%% TP 3%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.09%% TP 3%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.09 --tp-equity-pct 3 --skip-counter-trend > "sweep_year\buf009_tp3.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf009_tp3.txt.tmp" "buf009_tp3.txt" & echo    [saved] buf009_tp3.txt )
)
set /a N+=1
if exist "sweep_year\buf009_tp4.txt" (
    echo [!N!/12]  buf 0.09%% TP 4%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.09%% TP 4%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.09 --tp-equity-pct 4 --skip-counter-trend > "sweep_year\buf009_tp4.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf009_tp4.txt.tmp" "buf009_tp4.txt" & echo    [saved] buf009_tp4.txt )
)
set /a N+=1
if exist "sweep_year\buf012_tp3.txt" (
    echo [!N!/12]  buf 0.12%% TP 3%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.12%% TP 3%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.12 --tp-equity-pct 3 --skip-counter-trend > "sweep_year\buf012_tp3.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf012_tp3.txt.tmp" "buf012_tp3.txt" & echo    [saved] buf012_tp3.txt )
)
set /a N+=1
if exist "sweep_year\buf012_tp4.txt" (
    echo [!N!/12]  buf 0.12%% TP 4%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.12%% TP 4%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.12 --tp-equity-pct 4 --skip-counter-trend > "sweep_year\buf012_tp4.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf012_tp4.txt.tmp" "buf012_tp4.txt" & echo    [saved] buf012_tp4.txt )
)
set /a N+=1
if exist "sweep_year\buf015_tp3.txt" (
    echo [!N!/12]  buf 0.15%% TP 3%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.15%% TP 3%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.15 --tp-equity-pct 3 --skip-counter-trend > "sweep_year\buf015_tp3.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf015_tp3.txt.tmp" "buf015_tp3.txt" & echo    [saved] buf015_tp3.txt )
)
set /a N+=1
if exist "sweep_year\buf015_tp4.txt" (
    echo [!N!/12]  buf 0.15%% TP 4%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.15%% TP 4%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.15 --tp-equity-pct 4 --skip-counter-trend > "sweep_year\buf015_tp4.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf015_tp4.txt.tmp" "buf015_tp4.txt" & echo    [saved] buf015_tp4.txt )
)
set /a N+=1
if exist "sweep_year\buf018_tp3.txt" (
    echo [!N!/12]  buf 0.18%% TP 3%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.18%% TP 3%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.18 --tp-equity-pct 3 --skip-counter-trend > "sweep_year\buf018_tp3.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf018_tp3.txt.tmp" "buf018_tp3.txt" & echo    [saved] buf018_tp3.txt )
)
set /a N+=1
if exist "sweep_year\buf018_tp4.txt" (
    echo [!N!/12]  buf 0.18%% TP 4%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.18%% TP 4%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.18 --tp-equity-pct 4 --skip-counter-trend > "sweep_year\buf018_tp4.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf018_tp4.txt.tmp" "buf018_tp4.txt" & echo    [saved] buf018_tp4.txt )
)
set /a N+=1
if exist "sweep_year\buf021_tp3.txt" (
    echo [!N!/12]  buf 0.21%% TP 3%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.21%% TP 3%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.21 --tp-equity-pct 3 --skip-counter-trend > "sweep_year\buf021_tp3.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf021_tp3.txt.tmp" "buf021_tp3.txt" & echo    [saved] buf021_tp3.txt )
)
set /a N+=1
if exist "sweep_year\buf021_tp4.txt" (
    echo [!N!/12]  buf 0.21%% TP 4%% - done, SKIP
) else (
    echo [!N!/12]  buf 0.21%% TP 4%% - running...
    python backtest_replay.py --from 2025-06-12 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.21 --tp-equity-pct 4 --skip-counter-trend > "sweep_year\buf021_tp4.txt.tmp" 2>&1
    if errorlevel 1 ( echo    ERROR ) else ( ren "sweep_year\buf021_tp4.txt.tmp" "buf021_tp4.txt" & echo    [saved] buf021_tp4.txt )
)

set OUT=sweep_year\_SWEEP_YEAR_SUMMARY.txt
echo QGAI FULL-YEAR SWEEP SUMMARY > %OUT%
echo Period: 2025-06-12 to 2026-06-12 >> %OUT%
echo. >> %OUT%
echo ##### buffer 0.06%% ^| equity-TP 3%% ##### >> %OUT%
if exist "sweep_year\buf006_tp3.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf006_tp3.txt" >> %OUT% )
echo. >> %OUT%
echo ##### buffer 0.06%% ^| equity-TP 4%% ##### >> %OUT%
if exist "sweep_year\buf006_tp4.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf006_tp4.txt" >> %OUT% )
echo. >> %OUT%
echo ##### buffer 0.09%% ^| equity-TP 3%% ##### >> %OUT%
if exist "sweep_year\buf009_tp3.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf009_tp3.txt" >> %OUT% )
echo. >> %OUT%
echo ##### buffer 0.09%% ^| equity-TP 4%% ##### >> %OUT%
if exist "sweep_year\buf009_tp4.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf009_tp4.txt" >> %OUT% )
echo. >> %OUT%
echo ##### buffer 0.12%% ^| equity-TP 3%% ##### >> %OUT%
if exist "sweep_year\buf012_tp3.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf012_tp3.txt" >> %OUT% )
echo. >> %OUT%
echo ##### buffer 0.12%% ^| equity-TP 4%% ##### >> %OUT%
if exist "sweep_year\buf012_tp4.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf012_tp4.txt" >> %OUT% )
echo. >> %OUT%
echo ##### buffer 0.15%% ^| equity-TP 3%% ##### >> %OUT%
if exist "sweep_year\buf015_tp3.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf015_tp3.txt" >> %OUT% )
echo. >> %OUT%
echo ##### buffer 0.15%% ^| equity-TP 4%% ##### >> %OUT%
if exist "sweep_year\buf015_tp4.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf015_tp4.txt" >> %OUT% )
echo. >> %OUT%
echo ##### buffer 0.18%% ^| equity-TP 3%% ##### >> %OUT%
if exist "sweep_year\buf018_tp3.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf018_tp3.txt" >> %OUT% )
echo. >> %OUT%
echo ##### buffer 0.18%% ^| equity-TP 4%% ##### >> %OUT%
if exist "sweep_year\buf018_tp4.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf018_tp4.txt" >> %OUT% )
echo. >> %OUT%
echo ##### buffer 0.21%% ^| equity-TP 3%% ##### >> %OUT%
if exist "sweep_year\buf021_tp3.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf021_tp3.txt" >> %OUT% )
echo. >> %OUT%
echo ##### buffer 0.21%% ^| equity-TP 4%% ##### >> %OUT%
if exist "sweep_year\buf021_tp4.txt" ( findstr /C:"Total:" /C:"Profit factor" /C:"Max drawdown" /C:"Win rate" /C:"Trades " "sweep_year\buf021_tp4.txt" >> %OUT% )
echo. >> %OUT%

echo   DONE! Summary: %OUT%
notepad %OUT%
pause
