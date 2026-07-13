@echo off
setlocal
chcp 65001 >nul
title QGAI - LeakFix P1+P2+P3 : backup + retrain + BACKTEST SMOKE (30d)

REM =====================================================================
REM  SMOKE TEST (run this FIRST) — short 30-day backtest to verify the
REM  retrain + 3 leak fixes don't crash and the feature count is 34.
REM  Leakage-audit fixes (2026-07-12), all HONEST:
REM    P1  DROP corr_imp_ratio (35->34 feat)
REM    P2  ob_strength confirm shift(-1)->shift(-2)
REM    P3  news dev_norm -> expanding past-only z-score
REM
REM  Order: BACKUP (safety, before retrain) -> RETRAIN (34 feat) ->
REM         30-day CTF-OFF backtest.  Verify:
REM           - retrain prints 34 features (corr_imp_ratio gone)
REM           - no crash, backtest_report.txt appears
REM  If OK -> Run_LeakFix_P1P2P3_Retrain_Backtest.bat (full 1yr).
REM  Default honest — QGAI_INRANGE_LEGACY NOT set.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "MODELS=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\_backup_pre_leakfix_p1p2p3_20260712"
set "OUT=C:\QGAI\backtest\results\leakfix_p1p2p3_backtest_TEST"

cd /d "%ROOT%\engine"

echo ============================================================
echo   LeakFix P1+P2+P3 - SMOKE (backup + retrain + 30d backtest)
echo   Expect: 34 features (corr_imp_ratio dropped)
echo   %DATE% %TIME%
echo ============================================================
echo.

REM ---------- 1. BACKUP (before retrain) ----------
if exist "%BACKUP%" (
    echo [1/3] Backup already exists - skipping.
) else (
    echo [1/3] Backing up current model...
    xcopy /E /I /Y "%MODELS%" "%BACKUP%" >nul
    if errorlevel 1 goto fail
)
echo.

REM ---------- 2. RETRAIN (34 feat honest) ----------
echo [2/3] Retraining (34 feat, honest OB + news)...
"%PY%" train.py
if errorlevel 1 (
    echo *** RETRAIN FAILED - restore: xcopy /E /I /Y "%BACKUP%" "%MODELS%" ***
    goto fail
)
echo.

REM ---------- 3. BACKTEST 30d smoke ----------
echo [3/3] 30-day backtest smoke (CTF-OFF)...
set QGAI_CTF_FADE=0
"%PY%" "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "%OUT%"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   SMOKE DONE %DATE% %TIME%
echo   Check: feature count = 34, no crash, report at
echo     %OUT%\backtest_report.txt
echo   If OK -> Run_LeakFix_P1P2P3_Retrain_Backtest.bat (full 1yr)
echo   Model is now the 34-feat retrain (backup at %BACKUP%).
echo ============================================================
pause
exit /b 0

:fail
echo.
echo *** FAILED %DATE% %TIME% - restore: xcopy /E /I /Y "%BACKUP%" "%MODELS%" ***
pause
exit /b 1
