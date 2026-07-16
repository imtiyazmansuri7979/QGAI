@echo off
setlocal
chcp 65001 >nul
call "%~dp0..\_console_theme.bat"
title QGAI - FS67-13 TEST - Tier1 Drop Candidates OOS1Y Confirm (1 feature only)

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-13-TEST"
set "RESULT_ID=FS67-13_tier1_drop_candidates_oos1y_confirm_TEST"
set "QGAI_FEATURE_SWEEP_DIR=C:\QGAI\backtest\results\feature_sweep_67\%RESULT_ID%"
set "QGAI_FEATURE_SWEEP_RESULT_ID=%RESULT_ID%"
set "QGAI_SWEEP_BASELINE_JSON=C:\QGAI\backtest\results\feature_sweep_67\FS67-12_h4_support_oos1y_confirm\baseline\result.json"

REM Same window/cutoff as the real FS67-13 run -- this TEST only narrows
REM the feature list to 1, everything else is identical, so a clean TEST
REM run is a real error-check of the actual config (house rule: always
REM test-run before any long run).
set "QGAI_SWEEP_TRAIN_CUTOFF=2025-06-28"
set "QGAI_SWEEP_FROM=2025-06-29"
set "QGAI_SWEEP_TO=2026-06-29"

cd /d "%ROOT%\engine"

echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% - TIER1 DROP CANDIDATES OOS1Y CONFIRM - TEST%QGAI_RESET%
echo %QGAI_DIM%------------------------------------------------------------%QGAI_RESET%
echo %QGAI_WHITE%  Tests ONLY 1 feature (%QGAI_YELLOW%M15_ADX%QGAI_WHITE%) to verify:%QGAI_RESET%
echo     - no crash during baseline reuse + ablate retrain
echo     - leakage-guard PASS on this cutoff/window
echo     - result.json + SUMMARY.csv written to the right folder
echo     - this is a SEPARATE isolated result folder (_TEST suffix),
echo       does not touch or reuse the real FS67-13 folder
echo.
echo   Once this completes clean, run the FULL 6-feature FS67-13 bat.
echo.
echo %QGAI_CYAN%  Result folder:%QGAI_RESET%
echo   %QGAI_FEATURE_SWEEP_DIR%
echo %QGAI_CYAN%  Baseline reuse:%QGAI_RESET%
echo   %QGAI_SWEEP_BASELINE_JSON%
echo.
echo %QGAI_GREEN%  Live model is NOT touched.%QGAI_RESET%
echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%

"%PY%" run_feature_sweep.py --tier active --only M15_ADX
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto fail

echo.
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  TEST OK %RUN_ID%%QGAI_RESET%
echo   Summary: %QGAI_FEATURE_SWEEP_DIR%\%RESULT_ID%_SUMMARY.csv
echo   -^> If this looks correct, run FS67-13_RUN_Tier1DropCandidates_OOS1YConfirm.bat
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%
pause
exit /b 0

:fail
echo.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_RED%%QGAI_BOLD%  TEST FAILED %RUN_ID%%QGAI_RESET%
echo   Check logs in:
echo   %QGAI_FEATURE_SWEEP_DIR%
echo   Do NOT run the full FS67-13 bat until this is fixed.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
pause
exit /b %RC%
