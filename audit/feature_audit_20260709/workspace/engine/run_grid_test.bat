@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title QGAI - Grid Test 15 runs (resume-able)
color 0B
cls

set "ENGINE_DIR=%~dp0"
cd /d "%ENGINE_DIR%"

if not exist grid_results mkdir grid_results

echo ============================================================
echo   QGAI GRID TEST - 15 runs (RESUME-ABLE)
echo   If it crashes, just run again - finished tests are skipped
echo ============================================================
echo.

set /a N=0
for %%S in (6 7 8) do (
    for %%B in (0.11 0.14 0.17 0.20 0.23) do (
        set /a N+=1
        set "RESFILE=grid_results\buf%%B_sl%%S.txt"
        if exist "!RESFILE!" (
            echo [!N!/15]  buffer %%B%% ^| dailySL %%S%%   - already done, SKIP
        ) else (
            echo [!N!/15]  buffer %%B%% ^| dailySL %%S%%   - running...
            python backtest_replay.py --from 2025-06-01 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct %%B --daily-sl %%S > "!RESFILE!.tmp" 2>&1
            if errorlevel 1 (
                echo    ERROR on this run - see !RESFILE!.tmp
            ) else (
                ren "!RESFILE!.tmp" "buf%%B_sl%%S.txt"
                echo    [saved] buf%%B_sl%%S.txt
            )
        )
    )
)

echo.
echo ============================================================
echo   Combining all results...
echo ============================================================
set OUT=grid_results\_ALL_RESULTS.txt
echo QGAI GRID TEST - ALL RESULTS > %OUT%
echo Generated: %DATE% %TIME% >> %OUT%
for %%S in (6 7 8) do (
    for %%B in (0.11 0.14 0.17 0.20 0.23) do (
        echo. >> %OUT%
        echo ##### BUFFER %%B%% ^| DAILY SL %%S%% ##### >> %OUT%
        if exist "grid_results\buf%%B_sl%%S.txt" type "grid_results\buf%%B_sl%%S.txt" >> %OUT%
    )
)

echo   ALL DONE! Combined: %OUT%
notepad %OUT%
pause
