@echo off
setlocal
chcp 65001 >nul

REM =====================================================================
REM  SMMA MTF soft gate — LIVE-PARITY parity test (30-day TEST)
REM  Uses backtest_replay.py (live code path) with QGAI_SMMA_MTF=1.
REM  Verifies: gate wires cleanly, blocked_by=smma_mtf entries appear,
REM  files land in the right folder. Run BEFORE the FULL parity BT.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT=C:\QGAI\backtest\results\smma_parity_test\TEST_30d_smmaON"

set QGAI_SMMA_MTF=1

echo ============================================================
echo TEST: SMMA parity (live-parity backtest) 30-day, gate ON
echo Env: QGAI_SMMA_MTF=%QGAI_SMMA_MTF%
echo ============================================================
cd /d "%ROOT%\engine"
%PY% "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "%OUT%"
if errorlevel 1 goto fail

echo.
echo TEST DONE. Check %OUT%\backtest_report.txt + signals CSV blocked_by column.
echo If OK -^> run Run_SMMA_Parity_BT_FULL.bat
pause
exit /b 0

:fail
echo *** TEST FAILED — do NOT run FULL bat yet. ***
pause
exit /b 1
