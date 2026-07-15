@echo off
setlocal
chcp 65001 >nul
title QGAI - FS67-00 - Run All 67 Feature Sweep

set "ROOT=C:\QGAI"
set "RUNNER_DIR=%ROOT%\backtest\_runners\feature_sweep_67"

echo ============================================================
echo   FS67-00 - 67 FEATURE VALIDATION SWEEP - RUN ALL
echo ------------------------------------------------------------
echo   Runs:
echo     FS67-01 Priority Batch
echo     FS67-02 Tier1 Active
echo     FS67-03 Tier2 High Probability
echo     FS67-04 Tier3 Remaining
echo.
echo   Root results folder:
echo     C:\QGAI\backtest\results\feature_sweep_67
echo.
echo   Live model is NOT touched.
echo ============================================================

call "%RUNNER_DIR%\FS67-01_RUN_PriorityBatch.bat"
if errorlevel 1 goto fail

call "%RUNNER_DIR%\FS67-02_RUN_Tier1_Active.bat"
if errorlevel 1 goto fail

call "%RUNNER_DIR%\FS67-03_RUN_Tier2_HighProbability.bat"
if errorlevel 1 goto fail

call "%RUNNER_DIR%\FS67-04_RUN_Tier3_Remaining.bat"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   FS67-00 DONE - ALL 67 FEATURE SWEEP STAGES DONE
echo   Results: C:\QGAI\backtest\results\feature_sweep_67
echo ============================================================
pause
exit /b 0

:fail
echo.
echo ============================================================
echo   FS67-00 FAILED - stopped at the stage above.
echo   Re-run the same BAT later; each stage is resume-safe.
echo ============================================================
pause
exit /b 1
