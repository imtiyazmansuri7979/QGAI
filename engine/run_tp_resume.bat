@echo off
REM =====================================================================
REM  QGAI - FULL 1-YEAR BACKTEST - RESUMABLE TP SWEEP
REM  Checks if results already exist before running to prevent wasting time.
REM =====================================================================
setlocal enabledelayedexpansion
cd /d C:\QGAI\engine
REM Force UTF-8 so emoji in the report don't crash when output is saved to a file
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set FROM=2025-06-17
set TO=2026-06-16
set EQUITY=10000
set TPLIST=0.50 0.60 0.70 0.80 0.90 1.00 1.10 1.20 2.00 4.00

echo ================================================
echo   QGAI  -  RESUMABLE 1-YEAR BACKTEST  -  TP SWEEP
echo   From %FROM%   To %TO%
echo ================================================

for %%T in (%TPLIST%) do (
    echo.
    if exist logs\trades_tp_%%T.csv (
        echo [SKIP] --- price-TP %%T already completed. Skipping to next... ---
    ) else (
        echo --- Running FULL backtest : price-TP %%T%% ---
        python backtest_replay.py --from %FROM% --to %TO% --equity %EQUITY% --tp-cap %%T --tp-equity-pct 0 > results_tp_%%T.txt 2>&1
        if exist logs\backtest_trades.csv copy /Y logs\backtest_trades.csv logs\trades_tp_%%T.csv >nul
        echo      saved: results_tp_%%T.txt
    )
)

echo.
echo ================================================
echo   Building summary file...
echo ================================================
set SUMMARY=TP_SWEEP_SUMMARY.txt
echo QGAI TP Sweep  ^|  %FROM% to %TO%  ^|  Capital $%EQUITY%> %SUMMARY%
echo ====================================================>> %SUMMARY%
for %%T in (%TPLIST%) do (
    echo.>> %SUMMARY%
    echo == price-TP %%T ==>> %SUMMARY%
    if exist results_tp_%%T.txt (
        findstr /I "trades win profit drawdown total net avg" results_tp_%%T.txt>> %SUMMARY%
    ) else (
        echo Result text file missing, test may have skipped or failed.>> %SUMMARY%
    )
)

echo.
type %SUMMARY%
echo.
echo ================================================
echo Done.
echo   Summary (all)  : %SUMMARY%
echo   Full reports   : results_tp_*.txt
echo   Trade files    : logs\trades_tp_*.csv
echo ================================================
pause