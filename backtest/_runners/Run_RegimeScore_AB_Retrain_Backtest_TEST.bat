@echo off
setlocal
chcp 65001 >nul
title QGAI - RegimeScore A/B TEST

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_CTF_FADE=0"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "MODELS=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\_backup_pre_regimescore_restore_20260712"

cd /d "%ROOT%\engine"

echo ============================================================
echo   RegimeScore A/B TEST - 1 month
echo   A = WITHOUT 4 features (ablate, 35-feat)
echo   B = WITH 4 features (restore, 38-feat)
echo   %DATE% %TIME%
echo ============================================================
echo.

if exist "%BACKUP%" (
    echo Backup already exists - skipping.
) else (
    echo Backing up current model...
    xcopy /E /I /Y "%MODELS%" "%BACKUP%"
    if errorlevel 1 (
        echo XCOPY FAILED - check path
        pause
        exit /b 1
    )
    echo Backup done.
)

echo.
echo [A] Retrain WITHOUT 4 features...
set "QGAI_ABLATE=h4_trending_h1_aligned,h4_ranging_h1_neutral,h4_h1_regime_score,trade_direction"
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN A FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "C:\QGAI\backtest\results\regimescore_ab_TEST_A_without"
if errorlevel 1 (
    echo BACKTEST A FAILED
    pause
    exit /b 1
)

echo.
echo [B] Retrain WITH 4 features (default)...
set "QGAI_ABLATE="
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN B FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "C:\QGAI\backtest\results\regimescore_ab_TEST_B_with"
if errorlevel 1 (
    echo BACKTEST B FAILED
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   DONE %DATE% %TIME%
echo   A without: regimescore_ab_TEST_A_without\backtest_report.txt
echo   B with   : regimescore_ab_TEST_B_with\backtest_report.txt
echo   Model on disk = B (38-feat)
echo ============================================================
pause
exit /b 0
