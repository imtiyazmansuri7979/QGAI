@echo off
setlocal
chcp 65001 >nul
call "%~dp0..\_console_theme.bat"
title QGAI - FS67-22 - 15_min_slot + M15_ADX WFO 6M

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-22"
set "RESULT_ID=FS67-22_15minslot_m15adx_wfo6m_20251229_20260629"
set "BASELINE_DIR=C:\QGAI\backtest\results\%RESULT_ID%_baseline_with_features"
set "CANDIDATE_DIR=C:\QGAI\backtest\results\%RESULT_ID%_candidate_live_dropped"

cd /d "%ROOT%\engine"

echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% - 15_min_slot + M15_ADX - 6M WFO%QGAI_RESET%
echo %QGAI_DIM%------------------------------------------------------------%QGAI_RESET%
echo %QGAI_WHITE%  Context: both features were confirmed DROP_CANDIDATE on BOTH%QGAI_RESET%
echo   the FS67-02 3-month screen AND the FS67-13 1-year OOS1Y confirm.
echo   Imtiyaz already approved dropping them from live (features.py
echo   _MANUAL_PRUNE, 2026-07-16) -- this WFO run is PARALLEL due-diligence,
echo   not a live-adoption gate (the drop already happened).
echo.
echo %QGAI_CYAN%  Two arms:%QGAI_RESET%
echo   %QGAI_YELLOW%A) baseline_with_features%QGAI_RESET% -- QGAI_UNPRUNE=15_min_slot,M15_ADX
echo      (puts both features back, simulating the OLD live config)
echo   %QGAI_YELLOW%B) candidate_live_dropped%QGAI_RESET%  -- no unprune (today's actual live
echo      default, i.e. WITHOUT both features)
echo.
echo   Period: 2025-12-29 to 2026-06-29 (~6 months / weekly WFO) -- same
echo   window as FS67-21 for registry consistency.
echo.
echo   Both arms retrain in data\models\test_workspace only. Live model
echo   is NOT touched.
echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%

if exist "C:\QGAI\data\models\.training_lock" (
  echo.
  echo %QGAI_RED%%QGAI_BOLD%FAILED %RUN_ID%%QGAI_RESET%
  echo Training lock exists:
  echo   C:\QGAI\data\models\.training_lock
  echo If no train.py is running, delete the lock and rerun.
  pause
  exit /b 1
)

echo.
echo %QGAI_GREEN%[1/2] Running ARM A - baseline_with_features...%QGAI_RESET%
set "QGAI_UNPRUNE=15_min_slot,M15_ADX"
set "QGAI_ABLATE="
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"
"%PY%" run_wfo.py --start 2025-12-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir %RESULT_ID%_baseline_with_features
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto fail

echo.
echo %QGAI_GREEN%[2/2] Running ARM B - candidate_live_dropped...%QGAI_RESET%
set "QGAI_UNPRUNE="
set "QGAI_ABLATE="
"%PY%" run_wfo.py --start 2025-12-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir %RESULT_ID%_candidate_live_dropped
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto fail

echo.
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% DONE%QGAI_RESET%
echo ------------------------------------------------------------
echo   Baseline (with features)  : %BASELINE_DIR%\_WFO_SUMMARY.csv
echo   Candidate (live, dropped) : %CANDIDATE_DIR%\_WFO_SUMMARY.csv
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$base='%BASELINE_DIR%\_WFO_SUMMARY.csv'; $cand='%CANDIDATE_DIR%\_WFO_SUMMARY.csv';" ^
  "if((Test-Path $base) -and (Test-Path $cand)) {" ^
  "  $b=Import-Csv $base | ? { $_.week_start -match '^\d{4}-\d{2}-\d{2}$' };" ^
  "  $c=Import-Csv $cand | ? { $_.week_start -match '^\d{4}-\d{2}-\d{2}$' };" ^
  "  $br=($b | Measure-Object total_r -Sum).Sum; $cr=($c | Measure-Object total_r -Sum).Sum;" ^
  "  $bt=($b | Measure-Object trades -Sum).Sum; $ct=($c | Measure-Object trades -Sum).Sum;" ^
  "  $bp=($b | ? { [double]$_.total_r -gt 0 }).Count; $cp=($c | ? { [double]$_.total_r -gt 0 }).Count;" ^
  "  Write-Host ''; Write-Host 'WFO6M COMPARISON';" ^
  "  Write-Host ('With features (old)   : {0:N1}R | trades {1} | positive weeks {2}/{3}' -f $br,$bt,$bp,$b.Count);" ^
  "  Write-Host ('Without features (live): {0:N1}R | trades {1} | positive weeks {2}/{3}' -f $cr,$ct,$cp,$c.Count);" ^
  "  Write-Host ('Delta (live - old)     : {0:+0.0;-0.0;0.0}R' -f ($cr-$br));" ^
  "  Write-Host ''; Write-Host 'If Delta is negative, run the full BACKTEST_RESULT_AUDIT.md checklist';" ^
  "  Write-Host 'before deciding whether to revert the live drop.';" ^
  "} else { Write-Host 'Compare skipped: baseline or candidate summary missing.' }"

pause
exit /b 0

:fail
echo.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_RED%%QGAI_BOLD%  FAILED %RUN_ID%%QGAI_RESET%
echo   Check:
echo     %BASELINE_DIR%
echo     %CANDIDATE_DIR%
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
pause
exit /b %RC%
