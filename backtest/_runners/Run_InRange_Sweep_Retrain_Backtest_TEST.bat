@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title QGAI - in_range_phase threshold SWEEP - retrain + 1mo backtest

REM =====================================================================
REM  in_range_phase cutoff sweep (keep the clean BINARY, tune WHERE the
REM  line sits). Env QGAI_INRANGE_THRESH sets the |H4 move| cutoff.
REM  Values: 0.3 0.4 0.5(current) 0.6 0.7  -- each: retrain + 1mo backtest.
REM
REM  Read each report's Total R AND the "BY REGIME" block — if the best
REM  cutoff differs by regime (Ranging vs Trending vs Volatile), that tells
REM  us whether a REGIME-SPECIFIC threshold is worth building next.
REM
REM  Backup first; baseline (0.5, 35-feat +8.9R) restored at the end.
REM  Range/#2/#4 filters already removed. CTF off.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_CTF_FADE=0"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "MODELS=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\_backup_pre_rawmove_20260712"
set "BASE=--from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"

cd /d "%ROOT%\engine"

echo ============================================================
echo   in_range_phase THRESHOLD SWEEP - %DATE% %TIME%
echo ============================================================

if not exist "%BACKUP%" (
    echo *** Baseline backup missing: %BACKUP% - aborting for safety. ***
    pause
    exit /b 1
)

for %%T in (0.3 0.4 0.5 0.6 0.7) do (
    echo.
    echo ==== threshold %%T : retrain + backtest ====
    set "QGAI_INRANGE_THRESH=%%T"
    "%PY%" train.py
    if errorlevel 1 goto fail
    "%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\inrange_sweep_TEST_t%%T"
    if errorlevel 1 goto fail
)

echo.
echo Restoring baseline model (thresh 0.5, +8.9R)...
set "QGAI_INRANGE_THRESH="
xcopy /E /I /Y "%BACKUP%" "%MODELS%" >nul

echo.
echo ============================================================
echo   SWEEP DONE. Compare Total R + BY REGIME in:
echo     inrange_sweep_TEST_t0.3 / t0.4 / t0.5 / t0.6 / t0.7
echo   Best global cutoff -> adopt. Best differs by regime -> build
echo   a regime-specific in_range_phase next.
echo   Live model = baseline (0.5) restored.
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED %DATE% %TIME% - restoring baseline ***
xcopy /E /I /Y "%BACKUP%" "%MODELS%" >nul
pause
exit /b 1
