@echo off
setlocal
chcp 65001 >nul
title QGAI - Restore corr_imp_ratio: Retrain + WFO TEST (2 weeks)

REM =====================================================================
REM  corr_imp_ratio RESTORED (2026-07-11). Feature back in model (35 feat).
REM  SHORT TEST — retrain + 2-week WFO — verify no crash.
REM  Then run the FULL bat.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_CORE_ONLY=1"

cd /d "%ROOT%\engine"

echo ============================================================
echo   RESTORE corr_imp_ratio - TEST (retrain + 2-week WFO)
echo   Expected: 35 features (incl corr_imp_ratio)
echo   %DATE% %TIME%
echo ============================================================
echo.

REM ---------- 1. RETRAIN ----------
echo [1/2] Retraining model (35 features)...
"%PY%" train.py
if errorlevel 1 (
    echo *** RETRAIN FAILED ***
    pause
    exit /b 1
)
echo.

REM ---------- 2. WFO TEST (2 weeks) ----------
echo [2/2] WFO test (2 weeks only)...
"%PY%" run_wfo.py --start 2026-06-01 --end 2026-06-15 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir wfo_restore_corrimp_TEST

if errorlevel 1 (
    echo *** WFO TEST FAILED ***
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   TEST DONE. Check:
echo     - Feature count = 35 (incl corr_imp_ratio)
echo     - No crash, output files appear
echo   If OK: run Run_Restore_CorrImp_Retrain_WFO.bat (full)
echo ============================================================
pause
