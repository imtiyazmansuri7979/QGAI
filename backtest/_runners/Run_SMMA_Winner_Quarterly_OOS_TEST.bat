@echo off
setlocal
chcp 65001 >nul

REM =====================================================================
REM  SMMA-winner (linear W25/35/40 T70 max +0.06) — TEST run
REM  Short 30-day window to verify: no crash, files land in right folder.
REM  Run this BEFORE the FULL quarterly OOS bat.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT=C:\QGAI\backtest\_scripts\backtest_replay_entry_exit_combo_research.py"
set "OUT_ROOT=C:\QGAI\backtest\results\smma_winner_oos_quarterly"
set "OUT=%OUT_ROOT%\TEST_30d"

set "BASE_ARGS=--equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --research-trail-confirm-bars 2 --sell-early-confirm2-tv --max-open 1 --no-ctf-fade"
set "SMMA_ARGS=--smma-mtf-soft --smma-penalty-mode linear --smma-weight-m15 0.25 --smma-weight-h1 0.35 --smma-weight-h4 0.40 --smma-linear-target 70 --smma-max-penalty 0.06"

if not exist "%OUT_ROOT%" mkdir "%OUT_ROOT%"

echo ============================================================
echo TEST: SMMA winner  30-day smoke  2026-05-29 -^> 2026-06-29
echo ============================================================
cd /d "%ROOT%"
%PY% "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 %BASE_ARGS% %SMMA_ARGS% --out-dir "%OUT%"
if errorlevel 1 goto fail

echo.
echo TEST DONE. Check %OUT%\backtest_report.txt + backtest_summary_*.csv
echo If OK -^> run Run_SMMA_Winner_Quarterly_OOS_FULL.bat
pause
exit /b 0

:fail
echo *** TEST FAILED — do NOT run FULL bat yet. ***
pause
exit /b 1
