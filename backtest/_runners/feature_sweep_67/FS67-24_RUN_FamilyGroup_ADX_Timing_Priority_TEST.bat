@echo off
setlocal
chcp 65001 >nul
call "%~dp0..\_console_theme.bat"
title QGAI - FS67-24 TEST - Restore-Value (2 arms only, error check)

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-24-TEST"
set "RESULT_BASE=C:\QGAI\backtest\results\FS67-24_family_group_TEST"
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"
set "QGAI_TRAIN_CUTOFF=2025-12-28"

set "BT_FROM=2025-12-29"
set "BT_TO=2026-01-12"
set "BT_FLAGS=--equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.15 --tp-equity-pct 0 --tp-regime --fixed-lot 0.01 --max-open 1"

cd /d "%ROOT%\engine"

echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% - Quick error check (2 weeks only)%QGAI_RESET%
echo %QGAI_DIM%------------------------------------------------------------%QGAI_RESET%
echo   Runs baseline + 1 unprune arm on 2 weeks only.
echo   Purpose: verify no crashes, correct output files, QGAI_UNPRUNE works.
echo   NOT for performance comparison (too few trades).
echo.
echo   %QGAI_YELLOW%Estimated time: ~5 minutes (2 arms x ~2.5 min each: 2-week window)%QGAI_RESET%
echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%

if exist "C:\QGAI\data\models\.training_lock" (
  echo %QGAI_RED%Training lock exists. Delete if no train.py running.%QGAI_RESET%
  pause
  exit /b 1
)

echo.
echo %QGAI_GREEN%[1/4] Training baseline...%QGAI_RESET%
set "QGAI_ABLATE="
set "QGAI_UNPRUNE="
"%PY%" train.py
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[2/4] Backtesting baseline (2 weeks)...%QGAI_RESET%
"%PY%" backtest_replay.py --from %BT_FROM% --to %BT_TO% %BT_FLAGS% --out-dir "%RESULT_BASE%\A_baseline"
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[3/4] Training unprune ADX_DI (4 dropped features)...%QGAI_RESET%
set "QGAI_ABLATE="
set "QGAI_UNPRUNE=M15_ADX,M30_ADX,H1_ADX,adx_trend_count"
"%PY%" train.py
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[4/4] Backtesting unprune ADX_DI (2 weeks)...%QGAI_RESET%
"%PY%" backtest_replay.py --from %BT_FROM% --to %BT_TO% %BT_FLAGS% --out-dir "%RESULT_BASE%\E_unprune_adx_di"
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%%QGAI_BOLD%  TEST PASSED - no crashes, output files created%QGAI_RESET%
echo   Check: %RESULT_BASE%\A_baseline\backtest_report.txt
echo          %RESULT_BASE%\E_unprune_adx_di\backtest_report.txt
echo   If both exist and look correct, run the full FS67-24 bat.

pause
exit /b 0

:fail
echo.
echo %QGAI_RED%%QGAI_BOLD%  TEST FAILED at step above. Fix before running full FS67-24.%QGAI_RESET%
pause
exit /b 1
