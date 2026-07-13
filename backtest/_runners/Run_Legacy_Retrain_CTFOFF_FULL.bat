@echo off
setlocal
chcp 65001 >nul
title QGAI - LEGACY retrain + CTF-OFF backtest - FULL 1yr (reproduce +384.5R)

REM =====================================================================
REM  Reproduce +384.5R with END-TO-END leaky parity: TRAIN and INFER both
REM  with leaky in_range_phase (QGAI_INRANGE_LEGACY=1) = matches the
REM  original 2026-07-07 model + backtest.
REM
REM  Original result to match: +384.5R / 673 trades / WR 62.7% / PF 3.43
REM
REM  Steps:
REM    1. BACKUP current honest model  -> _backup_honest_35feat_20260711
REM    2. RETRAIN with QGAI_INRANGE_LEGACY=1  (leaky training)
REM    3. BACKTEST full year CTF-OFF with QGAI_INRANGE_LEGACY=1
REM    4. RESTORE honest model  (live must NOT keep the leaky model)
REM
REM  Run Run_Legacy_Retrain_CTFOFF_TEST.bat FIRST.
REM
REM  WARNING: the +384.5R comes partly from lookahead; live cannot
REM  reproduce it. This bat leaves the LIVE model honest (step 4).
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "MODELS=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\_backup_honest_35feat_20260711"
set "OUT=C:\QGAI\backtest\results\legacy_retrain_ctfoff_FULL_1yr"

cd /d "%ROOT%\engine"

echo ============================================================
echo   LEGACY retrain + CTF-OFF - FULL 1yr (expect ~+384.5R)
echo   %DATE% %TIME%
echo ============================================================

REM --- 1. BACKUP honest model ---
if exist "%BACKUP%" (
    echo [1/4] Honest backup already exists - skipping.
) else (
    echo [1/4] Backing up current honest model...
    xcopy /E /I /Y "%MODELS%" "%BACKUP%" >nul
    if errorlevel 1 goto fail
)

REM --- 2. LEGACY retrain ---
echo [2/4] Retraining with QGAI_INRANGE_LEGACY=1 (leaky)...
set QGAI_INRANGE_LEGACY=1
"%PY%" train.py
if errorlevel 1 (
    echo *** RETRAIN FAILED - restoring honest model ***
    goto restore_and_fail
)

REM --- 3. LEGACY backtest full year ---
echo [3/4] Full-year CTF-OFF backtest (legacy)...
set QGAI_CTF_FADE=0
set QGAI_INRANGE_LEGACY=1
"%PY%" "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "%OUT%"
if errorlevel 1 goto restore_and_fail

REM --- 4. RESTORE honest model ---
echo [4/4] Restoring honest model (live safe)...
xcopy /E /I /Y "%BACKUP%" "%MODELS%" >nul
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   DONE %DATE% %TIME%
echo   Results: %OUT%\backtest_report.txt
echo   Compare Total R vs original +384.5R.
echo   Honest model RESTORED (live safe).
echo ============================================================
pause
exit /b 0

:restore_and_fail
echo *** Restoring honest model after failure... ***
xcopy /E /I /Y "%BACKUP%" "%MODELS%" >nul
:fail
echo *** FAILED %DATE% %TIME% - honest model at %BACKUP% ***
pause
exit /b 1
