@echo off
setlocal
chcp 65001 >nul
title QGAI - ADXMIG-01 - MT5 iADX() Parity Test - Step 1 (Python export)

REM =====================================================================
REM  Registry ID: ADXMIG-01  (adx_ema_migration work stream)
REM
REM  Exports the Python-computed EMA ADX(14) for M15/M30/H1/H4 (last 200
REM  closed bars) to CSV. This is HALF of the MT5 parity test — the other
REM  half requires running export_mt5_adx_for_parity.mq5 AS A SCRIPT
REM  inside the actual MT5 terminal (Claude cannot connect to a live MT5
REM  terminal, so this step must be run manually).
REM
REM  Full sequence:
REM    1. THIS BAT — produces adx_python_export.csv
REM    2. In MT5: compile engine\export_mt5_adx_for_parity.mq5 (Scripts
REM       folder), attach to an XAUUSD chart, run it -> writes
REM       adx_mt5_export.csv to MQL5\Files\
REM    3. Copy adx_mt5_export.csv next to adx_python_export.csv (this
REM       run's result folder), then run compare_adx_parity.py for the
REM       PASS/FAIL verdict.
REM
REM  Estimated time: ~10 seconds (step 1 only)
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "OUT_DIR=%ROOT%\backtest\results\adx_ema_migration\ADXMIG-01_mt5_parity_test"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
cd /d "%ROOT%\engine"

echo ============================================================
echo   ADXMIG-01 Step 1 - Python EMA ADX export
echo   Output: %OUT_DIR%\adx_python_export.csv
echo ============================================================

"%PY%" export_python_adx_for_mt5_parity.py --bars 200 --out "%OUT_DIR%\adx_python_export.csv"

echo.
echo ============================================================
echo   Step 1 DONE.
echo   NEXT (manual, in MT5 terminal):
echo     1. Open MetaEditor, create a new Script, paste the contents of
echo        %ROOT%\engine\export_mt5_adx_for_parity.mq5
echo     2. Compile (F7), then drag the script onto an XAUUSD chart
echo     3. It writes MQL5\Files\adx_mt5_export.csv
echo     4. Copy that file into: %OUT_DIR%
echo     5. Run: python "%ROOT%\engine\compare_adx_parity.py" --python "%OUT_DIR%\adx_python_export.csv" --mt5 "%OUT_DIR%\adx_mt5_export.csv"
echo ============================================================
pause
exit /b 0
