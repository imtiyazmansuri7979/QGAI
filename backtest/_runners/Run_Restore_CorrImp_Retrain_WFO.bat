@echo off
setlocal
chcp 65001 >nul
title QGAI - Restore corr_imp_ratio: Retrain + FULL WFO (53 weeks)

REM =====================================================================
REM  corr_imp_ratio RESTORED (2026-07-11, Imtiyaz).
REM  Was removed 07-09 based on Fable-5 "leakage" claim WITHOUT WFO gate.
REM  +444.7R dropped to +80.5R. Restoring to recover the proven baseline.
REM
REM  This bat:
REM    1. Backs up current models (safety)
REM    2. Retrains on 35-feature set (corr_imp_ratio back in)
REM    3. Full 53-week WFO — GATE: >= +400R (expect ~+444.7R)
REM
REM  ~2-3 hours total. Resume-safe WFO.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "MODELS=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\_backup_pre_restore_corrimp_20260711"

cd /d "%ROOT%\engine"

echo ============================================================
echo   RESTORE corr_imp_ratio - FULL RETRAIN + WFO
echo   Expected: 35 features, WFO >= +400R (was +444.7R)
echo   %DATE% %TIME%
echo ============================================================
echo.

REM ---------- 1. BACKUP ----------
if exist "%BACKUP%" (
    echo Backup already exists at %BACKUP% - skipping.
) else (
    echo [1/3] Backing up current models...
    xcopy /E /I /Y "%MODELS%" "%BACKUP%" >nul
    if errorlevel 1 goto fail
)
echo.

REM ---------- 2. RETRAIN ----------
echo [2/3] Retraining model (35 features incl corr_imp_ratio)...
"%PY%" train.py
if errorlevel 1 (
    echo *** RETRAIN FAILED - restore: xcopy /E /I /Y "%BACKUP%" "%MODELS%" ***
    goto fail
)
echo.

REM ---------- 3. FULL WFO ----------
echo [3/3] Full WFO (53 weeks, 2025-06-23 to 2026-06-29)...
"%PY%" run_wfo.py --start 2025-06-23 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir wfo_restore_corrimp_20260711

if errorlevel 1 goto fail

echo.
echo ============================================================
echo   DONE %DATE% %TIME%
echo   Results: backtest\results\wfo_restore_corrimp_20260711\
echo   GATE: >= +400R to confirm restore worked.
echo   If PASS: corr_imp_ratio stays, this is the new baseline.
echo   If FAIL: investigate further (restore backup).
echo     xcopy /E /I /Y "%BACKUP%" "%MODELS%"
echo ============================================================
pause
exit /b 0

:fail
echo.
echo *** FAILED %DATE% %TIME% ***
echo   Restore models: xcopy /E /I /Y "%BACKUP%" "%MODELS%"
pause
exit /b 1
