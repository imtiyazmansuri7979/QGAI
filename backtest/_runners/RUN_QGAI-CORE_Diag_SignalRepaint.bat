@echo off
setlocal EnableExtensions
chcp 65001 >nul
title QGAI-CORE Diag Signal Repaint

REM =====================================================================
REM  Signal-repaint audit (spec 2026-07-14): proves saved historical
REM  signals never change direction/probability/score/state/threshold/
REM  model-version/feature-snapshot after the fact.
REM
REM  This is a STEP-BASED diagnostic across REAL elapsed time -- run it
REM  once per step, at the point in time each step names:
REM    1. baseline            - run this FIRST, right after a live inference
REM                             cycle, to snapshot the current signal_ids.
REM    2. after15m            - run 15 minutes after baseline.
REM    3. after1h             - run 1 hour after baseline.
REM    4. after_restart       - restart the QGAI bridge, THEN run this.
REM    5. after_model_reload  - trigger a model retrain/reload, THEN run this.
REM    6. refresh_compare     - refresh the dashboard, THEN run this.
REM  Each step re-reads the SAME signal_ids from SQLite/CSV/dashboard.json
REM  and checks nothing that must be immutable has changed.
REM
REM  Usage:  RUN_QGAI-CORE_Diag_SignalRepaint.bat [step]
REM  With no argument, it auto-picks: "baseline" if no ledger exists yet,
REM  else the next step not yet run. Pass a step name explicitly to control
REM  exactly which one runs (e.g. when you're ready to do it out of order).
REM
REM  READ-ONLY: every DB access is a SELECT. Never mutates the signals
REM  table, never touches model files, never changes trading logic.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT=%ROOT%\engine\diag_signal_repaint.py"
set "OUT=%ROOT%\results\QGAI-CORE_Diag_SignalRepaint"
set "STEP=%~1"

echo ============================================================
echo   QGAI-CORE_Diag_SignalRepaint
echo ------------------------------------------------------------
echo   Audits historical signal repaint / overwrite / disappear.
if not "%STEP%"=="" (
    echo   Step: %STEP%
) else (
    echo   Step: auto (baseline if new, else next unrun step)
)
echo   Writes:
echo     %OUT%
echo ============================================================
echo.

if not exist "%PY%" (
    echo ERROR: Python not found:
    echo   %PY%
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo ERROR: Script not found:
    echo   %SCRIPT%
    pause
    exit /b 1
)

cd /d "%ROOT%" || (
    echo ERROR: Cannot open ROOT:
    echo   %ROOT%
    pause
    exit /b 1
)

if "%STEP%"=="" (
    "%PY%" "%SCRIPT%"
) else (
    "%PY%" "%SCRIPT%" --step %STEP%
)
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
    echo PASS - no repaint found across all steps run so far.
) else (
    echo CHECK DETAILS - see report and CSV files.
)
echo.
echo Results:
echo   %OUT%
echo.
echo Next: run the remaining steps at their real time offsets (see header
echo comments in this bat) to complete the full audit.
echo.
pause
exit /b %RC%
