@echo off
setlocal
chcp 65001 >nul
title QGAI - LEGACY retrain + CTF-OFF backtest - SMOKE TEST (30d)

REM =====================================================================
REM  Reproduce +384.5R properly: TRAIN and INFER both with leaky
REM  in_range_phase (QGAI_INRANGE_LEGACY=1) = end-to-end parity with the
REM  original 2026-07-07 model.
REM
REM  SMOKE (30d) to verify: backup ok, legacy retrain runs, 30d backtest
REM  produces a report, honest model restored at the end.
REM
REM  Steps:
REM    1. BACKUP current honest model  -> _backup_honest_35feat_20260711
REM    2. RETRAIN with QGAI_INRANGE_LEGACY=1  (leaky training)
REM    3. BACKTEST 30d CTF-OFF with QGAI_INRANGE_LEGACY=1
REM    4. RESTORE honest model  (live must NOT keep the leaky model)
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "MODELS=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\_backup_honest_35feat_20260711"
set "OUT=C:\QGAI\backtest\results\legacy_retrain_ctfoff_TEST"

cd /d "%ROOT%\engine"

echo ============================================================
echo   LEGACY retrain + CTF-OFF - SMOKE (30d)
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

REM --- 3. LEGACY backtest 30d ---
echo [3/4] 30d CTF-OFF backtest (legacy)...
set QGAI_CTF_FADE=0
set QGAI_INRANGE_LEGACY=1
"%PY%" "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "%OUT%"
if errorlevel 1 goto restore_and_fail

REM --- 4. RESTORE honest model ---
echo [4/4] Restoring honest model (live safe)...
xcopy /E /I /Y "%BACKUP%" "%MODELS%" >nul
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   SMOKE DONE. Check %OUT%\backtest_report.txt
echo   Honest model RESTORED. If OK: run Run_Legacy_Retrain_CTFOFF_FULL.bat
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
