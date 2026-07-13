@echo off
setlocal
chcp 65001 >nul
title QGAI - LeakFix P1+P2+P3 : FULL WFO (53 weeks) - honest gate

REM =====================================================================
REM  STEP 2 of 2 — WFO honest gate (run AFTER the backtest step).
REM  Uses the 34-feat honest model already retrained by
REM  Run_LeakFix_P1P2P3_Retrain_Backtest.bat.  (This bat does NOT retrain.)
REM
REM  GATE: honest baseline ~+80R (W13 corr_imp-out = +80.5R).
REM  PASS if Total R >= ~+78R (within noise) -> adopt P1+P2+P3.
REM  Big drop -> a fix cut real signal -> investigate before adopting.
REM
REM  ~2-3 hours. Resume-safe. Default honest — QGAI_INRANGE_LEGACY NOT set.
REM  Safety: if you did NOT run the backtest bat first, the model may not
REM  be the 34-feat retrain — run that bat first.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "BACKUP=C:\QGAI\data\models\_backup_pre_leakfix_p1p2p3_20260712"

cd /d "%ROOT%\engine"

echo ============================================================
echo   LeakFix P1+P2+P3 - FULL WFO (53 weeks)
echo   Gate: Total R >= ~+78R (honest baseline ~+80R)
echo   %DATE% %TIME%
echo ============================================================
echo.

if not exist "%BACKUP%" (
    echo *** WARNING: backup %BACKUP% not found.
    echo *** Did you run Run_LeakFix_P1P2P3_Retrain_Backtest.bat first?
    echo *** That bat backs up + retrains the 34-feat model this WFO needs.
    pause
)

echo Running full WFO (2025-06-23 to 2026-06-29)...
"%PY%" run_wfo.py --start 2025-06-23 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir wfo_leakfix_p1p2p3_20260712
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   DONE %DATE% %TIME%
echo   Results: backtest\results\wfo_leakfix_p1p2p3_20260712\
echo   GATE: Total R >= ~+78R => adopt P1+P2+P3 (honest baseline).
echo   If big drop: investigate which fix cut signal.
echo   REVERT models: xcopy /E /I /Y "%BACKUP%" "%MODELS%"
echo ============================================================
pause
exit /b 0

:fail
echo.
echo *** FAILED %DATE% %TIME% ***
echo   Restore models: xcopy /E /I /Y "%BACKUP%" "C:\QGAI\data\models\final"
pause
exit /b 1
