@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title QGAI - TP Cap Test (resume-able)
color 0B
cls

set "ENGINE_DIR=%~dp0"
cd /d "%ENGINE_DIR%"

if not exist tpcap_results mkdir tpcap_results

echo ============================================================
echo   QGAI TP CAP TEST - 2%% 3%% 4%% 5%% 6%%
echo   buffer 0.06%%, ratchet ON, risk 3%%, spread 0.20
echo   (resume-able - finished tests are skipped)
echo ============================================================
echo.

set /a N=0
for %%T in (2 3 4 5 6) do (
    set /a N+=1
    set "RESFILE=tpcap_results\tpcap%%T.txt"
    if exist "!RESFILE!" (
        echo [!N!/5]  TP cap %%T%%   - already done, SKIP
    ) else (
        echo [!N!/5]  TP cap %%T%%   - running...
        python backtest_replay.py --from 2025-06-01 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.06 --tp-cap %%T > "!RESFILE!.tmp" 2>&1
        if errorlevel 1 (
            echo    ERROR - see !RESFILE!.tmp
        ) else (
            ren "!RESFILE!.tmp" "tpcap%%T.txt"
            echo    [saved] tpcap%%T.txt
        )
    )
)

echo.
echo ============================================================
echo   Combining results...
echo ============================================================
set OUT=tpcap_results\_ALL_TPCAP.txt
echo QGAI TP CAP TEST - ALL RESULTS > %OUT%
echo Generated: %DATE% %TIME% >> %OUT%
for %%T in (2 3 4 5 6) do (
    echo. >> %OUT%
    echo ##### TP CAP %%T%% ##### >> %OUT%
    if exist "tpcap_results\tpcap%%T.txt" type "tpcap_results\tpcap%%T.txt" >> %OUT%
)

echo   ALL DONE! Combined: %OUT%
notepad %OUT%
pause
