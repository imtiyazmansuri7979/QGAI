@echo off
setlocal
chcp 65001 >nul
title QGAI - OOS1Y-01 - Current Config CLEAN OOS 1yr Backtest

REM =====================================================================
REM  CLEAN OOS 1-year single-training backtest.
REM
REM  This fixes the "IN-SAMPLE MODE / Leakage check: FAIL" issue from
REM  Run_CurrentLiveModel_Backtest_1yr.bat by training a fresh model with
REM  QGAI_TRAIN_CUTOFF set strictly BEFORE the backtest window.
REM
REM  SAFE: model files are written to data\models\test_workspace via
REM  QGAI_MODELS_DIR. data\models\final live model is NOT touched.
REM
REM  Train cutoff : 2025-06-28
REM  Backtest     : 2025-06-29 -> 2026-06-29
REM  Expected     : Leakage check PASS, no --allow-in-sample.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"
set "QGAI_TRAIN_CUTOFF=2025-06-28"
set "RUN_ID=OOS1Y-01"
set "RESULT_ID=OOS1Y-01_current_config_clean_oos_1yr_20260715"
set "OUT=C:\QGAI\backtest\results\%RESULT_ID%"

cd /d "%ROOT%\engine"

echo ============================================================
echo   %RUN_ID% - CURRENT CONFIG - CLEAN OOS 1yr BACKTEST
echo ------------------------------------------------------------
echo   SAFE: retrain goes to data\models\test_workspace only.
echo   Live model data\models\final is NOT touched.
echo.
echo   Train cutoff : %QGAI_TRAIN_CUTOFF%
echo   Backtest     : 2025-06-29 to 2026-06-29
echo   Expected     : Leakage check PASS
echo.
echo   Instructions:
echo   - Clean single-training OOS reference.
echo   - Retrains in test_workspace only; live final model is not touched.
echo   - Use as master 1-year baseline, not as feature-sweep local baseline.
echo   - If leakage check fails, do not trust the result.
echo ============================================================

echo.
echo [1/2] Retraining cutoff-safe model...
"%PY%" train.py
if errorlevel 1 goto fail

echo.
echo [2/2] Running clean OOS backtest...
"%PY%" backtest_replay.py --from 2025-06-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "%OUT%"
if errorlevel 1 goto fail

call :registry_names

echo.
echo ============================================================
echo   DONE %DATE% %TIME%
echo   Results: %OUT%
echo   Summary: %OUT%\%RESULT_ID%_001_summary_st-htf.csv
echo   This is the clean single-training OOS reference.
echo ============================================================
pause
exit /b 0

:fail
echo.
echo *** FAILED %DATE% %TIME% ***
echo   Live model was not touched; retrain used test_workspace.
pause
exit /b 1

:registry_names
if exist "%OUT%\backtest_report.txt" ren "%OUT%\backtest_report.txt" "%RESULT_ID%_000_report.txt"
if exist "%OUT%\backtest_summary_st-htf.csv" ren "%OUT%\backtest_summary_st-htf.csv" "%RESULT_ID%_001_summary_st-htf.csv"
if exist "%OUT%\backtest_trades_st-htf.csv" ren "%OUT%\backtest_trades_st-htf.csv" "%RESULT_ID%_002_trades_st-htf.csv"
if exist "%OUT%\backtest_signals_st-htf.csv" ren "%OUT%\backtest_signals_st-htf.csv" "%RESULT_ID%_003_signals_st-htf.csv"
exit /b 0
