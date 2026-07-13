@echo off
setlocal
chcp 65001 >nul
title QGAI - RAW H4-move feature A/B - retrain + SMOKE (1 month)

REM =====================================================================
REM  "model over hard filters" feature fix (2026-07-12): added RAW
REM  continuous h4_move_pct + cum3_move_pct so the model learns its OWN
REM  range / big-move cutoff instead of the hardcoded 0.5% / 2.0% binaries.
REM
REM  A = WITHOUT raw (QGAI_ABLATE drops them) — baseline
REM  B = WITH raw (normal)                    — the fix
REM
REM  Each variant: retrain then 1-month backtest. Backup first (safety).
REM  Range/#2/#4 filters already removed (current live). CTF off.
REM  B Total R > A AND WR healthy -> keep raw features (adopt).
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
echo   RAW H4-move feature A/B - retrain + 1mo backtest
echo   %DATE% %TIME%
echo ============================================================

if exist "%BACKUP%" ( echo Backup exists - skip. ) else (
    echo Backing up current model...
    xcopy /E /I /Y "%MODELS%" "%BACKUP%" >nul
    if errorlevel 1 goto fail
)

echo.
echo [A] retrain WITHOUT raw (ablate h4_move_pct,cum3_move_pct)...
set QGAI_ABLATE=h4_move_pct,cum3_move_pct
"%PY%" train.py
if errorlevel 1 goto fail
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\rawmove_ab_TEST_A_noraw"
if errorlevel 1 goto fail

echo.
echo [B] retrain WITH raw (the fix)...
set QGAI_ABLATE=
"%PY%" train.py
if errorlevel 1 goto fail
"%PY%" "%SCRIPT%" %BASE% --out-dir "C:\QGAI\backtest\results\rawmove_ab_TEST_B_withraw"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   DONE. Compare Total R + WR + trades:
echo     A no-raw : rawmove_ab_TEST_A_noraw\backtest_report.txt
echo     B with-raw: rawmove_ab_TEST_B_withraw\backtest_report.txt
echo   B > A on R AND WR healthy -> keep raw features.
echo   (Model left = B/with-raw. REVERT: xcopy /E /I /Y "%BACKUP%" "%MODELS%")
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED %DATE% %TIME% - restore: xcopy /E /I /Y "%BACKUP%" "%MODELS%" ***
pause
exit /b 1
