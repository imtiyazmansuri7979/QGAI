@echo off
title QGAI - Monte Carlo Risk Sweep
color 0B
cls

set "ENGINE_DIR=%~dp0"
cd /d "%ENGINE_DIR%"

echo ============================================================
echo   QGAI - MONTE CARLO RISK SWEEP (2%% to 8%%)
echo   Ratchet ON ^| fixed 0.06%% buffer ^| spread 0.20
echo ============================================================
echo.

echo [Step 1] Refreshing backtest CSV (fixed 0.06%%, ratchet ON)...
python backtest_replay.py --from 2025-06-01 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on > mc_backtest.log 2>&1
if errorlevel 1 (
    echo ERROR: backtest failed! Check mc_backtest.log
    pause
    exit /b 1
)
echo          done.
echo.
echo [Step 2] Running 7 Monte Carlo simulations (risk 2-8%%)...
echo          ^(showing on screen AND saving to mc_results.txt^)
echo.

echo QGAI MONTE CARLO RISK SWEEP > mc_results.txt
echo Generated: %DATE% %TIME% >> mc_results.txt
echo. >> mc_results.txt

for %%R in (2 3 4 5 6 7 8) do (
    echo ############### RISK %%R%% ############### >> mc_results.txt
    python monte_carlo.py --equity 10000 --risk %%R --runs 10000 >> mc_results.txt 2>&1
    echo. >> mc_results.txt
    echo   [done] risk %%R%%  - results appended
)

echo.
echo ============================================================
echo   ALL DONE!  Full results in:  mc_results.txt
echo   Opening it now...
echo ============================================================
notepad mc_results.txt
pause
