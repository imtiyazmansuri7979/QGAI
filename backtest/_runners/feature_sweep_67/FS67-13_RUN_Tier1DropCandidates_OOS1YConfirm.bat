@echo off
setlocal
chcp 65001 >nul
call "%~dp0..\_console_theme.bat"
title QGAI - FS67-13 - Tier1 Drop Candidates OOS1Y Confirm

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-13"
set "RESULT_ID=FS67-13_tier1_drop_candidates_oos1y_confirm"
set "QGAI_FEATURE_SWEEP_DIR=C:\QGAI\backtest\results\feature_sweep_67\%RESULT_ID%"
set "QGAI_FEATURE_SWEEP_RESULT_ID=%RESULT_ID%"
set "QGAI_SWEEP_BASELINE_JSON=C:\QGAI\backtest\results\feature_sweep_67\FS67-12_h4_support_oos1y_confirm\baseline\result.json"
set "FS67_13_TEST_DIR=C:\QGAI\backtest\results\feature_sweep_67\FS67-13_tier1_drop_candidates_oos1y_confirm_TEST"

REM Same window/cutoff as OOS1Y-01 so this compares apples-to-apples.
set "QGAI_SWEEP_TRAIN_CUTOFF=2025-06-28"
set "QGAI_SWEEP_FROM=2025-06-29"
set "QGAI_SWEEP_TO=2026-06-29"

cd /d "%ROOT%\engine"

echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% - TIER1 DROP CANDIDATES - OOS1Y CONFIRM%QGAI_RESET%
echo %QGAI_DIM%------------------------------------------------------------%QGAI_RESET%
echo %QGAI_WHITE%  Tests the 6 FS67-02 DROP_CANDIDATE features (3-month screen%QGAI_RESET%
echo   showed R improved when each was removed):
echo     %QGAI_YELLOW%ts_bars_since_flip%QGAI_RESET%   (+4.5R on 3-month screen)
echo     %QGAI_YELLOW%15_min_slot%QGAI_RESET%          (+3.1R on 3-month screen)
echo     %QGAI_YELLOW%M15_DI_diff%QGAI_RESET%          (+3.3R on 3-month screen)
echo     %QGAI_YELLOW%slot_cos%QGAI_RESET%             (+2.3R on 3-month screen)
echo     %QGAI_YELLOW%mins_to_next_3star%QGAI_RESET%   (+1.5R on 3-month screen)
echo     %QGAI_YELLOW%M15_ADX%QGAI_RESET%              (+6.8R on OOS1Y TEST, DROP_CANDIDATE)
echo.
echo %QGAI_CYAN%  Resume/cache rule:%QGAI_RESET%
echo   - %QGAI_GREEN%M15_ADX was already confirmed in FS67-13 TEST.%QGAI_RESET%
echo   - If that TEST result exists, this bat copies it into the full result
echo     folder first, so run_feature_sweep.py SKIPS rerunning M15_ADX but
echo     still includes it in the final full summary.
echo.
echo %QGAI_MAGENTA%  NOTE:%QGAI_RESET% in_range_phase was ALSO a DROP_CANDIDATE on FS67-02 but is
echo   EXCLUDED here on purpose -- Imtiyaz already decided (2026-07-16)
echo   to keep it as-is (deliberately accepted train/serve mismatch).
echo   Do not re-litigate that decision via this runner.
echo.
echo %QGAI_CYAN%  Baseline match:%QGAI_RESET%
echo     OOS1Y-01 current-config clean OOS 1yr
echo %QGAI_CYAN%  Baseline reuse:%QGAI_RESET%
echo     %QGAI_SWEEP_BASELINE_JSON%
echo.
echo %QGAI_CYAN%  Train cutoff :%QGAI_RESET% %QGAI_YELLOW%%QGAI_SWEEP_TRAIN_CUTOFF%%QGAI_RESET%
echo %QGAI_CYAN%  Backtest     :%QGAI_RESET% %QGAI_YELLOW%%QGAI_SWEEP_FROM% to %QGAI_SWEEP_TO%%QGAI_RESET%
echo.
echo %QGAI_CYAN%  Result folder:%QGAI_RESET%
echo   %QGAI_FEATURE_SWEEP_DIR%
echo.
echo %QGAI_GREEN%  Live model is NOT touched.%QGAI_RESET%
echo.
echo %QGAI_CYAN%  Instructions:%QGAI_RESET%
echo   - Baseline is reused from FS67-12/OOS1Y; it is NOT rerun.
echo   - Each feature tested independently (ablate vs baseline), same
echo     mechanism as FS67-02, just on the 1-year OOS1Y window instead
echo     of the 3-month screen window.
echo   - A feature that flips to REGIME_OR_DIRECTIONAL_KEEP or
echo     CORE_KEEP here (i.e. hurts on the longer window) should NOT
echo     be dropped, even though the 3-month screen liked dropping it.
echo   - Only a feature that stays DROP_CANDIDATE on BOTH windows moves
echo     on to a full WFO confirmation before any live adoption.
echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%

if exist "%FS67_13_TEST_DIR%\ablate_M15_ADX\result.json" (
  if not exist "%QGAI_FEATURE_SWEEP_DIR%\ablate_M15_ADX\result.json" (
    echo.
    echo %QGAI_GREEN%[resume] Seeding cached M15_ADX result from FS67-13 TEST...%QGAI_RESET%
    mkdir "%QGAI_FEATURE_SWEEP_DIR%\ablate_M15_ADX" >nul 2>nul
    robocopy "%FS67_13_TEST_DIR%\ablate_M15_ADX" "%QGAI_FEATURE_SWEEP_DIR%\ablate_M15_ADX" /E >nul
    if errorlevel 8 goto seed_fail
  ) else (
    echo.
    echo %QGAI_GREEN%[resume] M15_ADX cached result already exists in full result folder.%QGAI_RESET%
  )
) else (
  echo.
  echo %QGAI_YELLOW%[resume] FS67-13 TEST M15_ADX result not found; full run will compute M15_ADX normally.%QGAI_RESET%
)

"%PY%" run_feature_sweep.py --tier active --only ts_bars_since_flip,15_min_slot,M15_DI_diff,slot_cos,mins_to_next_3star,M15_ADX
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto fail

echo.
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  DONE %RUN_ID%%QGAI_RESET%
echo   Summary: %QGAI_FEATURE_SWEEP_DIR%\%RESULT_ID%_SUMMARY.csv
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%
pause
exit /b 0

:seed_fail
echo.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_RED%%QGAI_BOLD%  FAILED %RUN_ID%%QGAI_RESET%
echo   Could not copy cached M15_ADX result from:
echo   %FS67_13_TEST_DIR%\ablate_M15_ADX
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
pause
exit /b 1

:fail
echo.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_RED%%QGAI_BOLD%  FAILED %RUN_ID%%QGAI_RESET%
echo   Check logs in:
echo   %QGAI_FEATURE_SWEEP_DIR%
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
pause
exit /b %RC%
