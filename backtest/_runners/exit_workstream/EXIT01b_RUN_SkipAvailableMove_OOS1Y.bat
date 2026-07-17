@echo off
setlocal
chcp 65001 >nul
title QGAI - EXIT01b - Skip Available Move Analysis (1-year OOS)

REM =====================================================================
REM  Registry ID: EXIT01b  (exit work stream)
REM
REM  Splits the total available move (sum of high-low for every M15 bar)
REM  into IN-TRADE vs SKIP. Shows how much price movement happens while
REM  the system has no position open — the theoretical ceiling for better
REM  entry timing.
REM
REM  READ-ONLY. No model, no retrain, no live impact. Pure pandas analysis
REM  over existing OHLC + trades CSV. Runs in ~30 seconds.
REM
REM  Estimated time: ~30 seconds
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "TRADES_CSV=%ROOT%\backtest\results\OOS1Y-01_current_config_clean_oos_1yr_20260715\OOS1Y-01_current_config_clean_oos_1yr_20260715_002_trades_st-htf.csv"
set "OUT_DIR=%ROOT%\backtest\results\exit_workstream\EXIT01b_skip_available_move_OOS1Y"

cd /d "%ROOT%\engine"

if not exist "%TRADES_CSV%" (
    echo ============================================================
    echo   ERROR: OOS1Y trades CSV not found:
    echo   %TRADES_CSV%
    echo   Run OOS1Y backtest first.
    echo ============================================================
    pause
    exit /b 1
)

echo ============================================================
echo   EXIT01b - SKIP AVAILABLE MOVE ANALYSIS (1-year OOS)
echo   Trades: %TRADES_CSV%
echo   Output: %OUT_DIR%
echo   %DATE% %TIME%
echo.
echo   Estimated time: ~30 seconds
echo ============================================================

"%PY%" analyze_skip_available_move.py --trades-csv "%TRADES_CSV%" --from 2025-06-29 --to 2026-06-29 --out-dir "%OUT_DIR%"
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   DONE. Results:
echo   %OUT_DIR%\skip_available_move_report.txt
echo   %OUT_DIR%\skip_available_move_summary.csv
echo   %OUT_DIR%\skip_available_move_by_hour.csv
echo ============================================================
pause
exit /b %RC%
