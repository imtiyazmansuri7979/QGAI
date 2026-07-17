@echo off
setlocal
chcp 65001 >nul
call "%~dp0..\_console_theme.bat"
title QGAI - FS67-23 - 15_min_slot + M15_ADX Single-Split H2 (retrain-frequency isolation)

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-23"
set "RESULT_ID=FS67-23_15minslot_m15adx_singlesplit_h2"
set "BASELINE_DIR=C:\QGAI\backtest\results\%RESULT_ID%_baseline_with_features"
set "CANDIDATE_DIR=C:\QGAI\backtest\results\%RESULT_ID%_candidate_live_dropped"
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"
set "QGAI_TRAIN_CUTOFF=2025-12-28"

cd /d "%ROOT%\engine"

echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% - 15_min_slot + M15_ADX - single-split H2 isolation%QGAI_RESET%
echo %QGAI_DIM%------------------------------------------------------------%QGAI_RESET%
echo %QGAI_WHITE%  Purpose: FS67-13 (static single-split, full year) said DROP these%QGAI_RESET%
echo   2 features; FS67-22 (6-month WFO, weekly retrain) said KEEP -- on
echo   the SAME 2025-12-29 to 2026-06-29 window. Fable-5 root-cause trace
echo   (2026-07-17) found this is a REAL conflict, not a period effect
echo   (FS67-13's own H2-only sub-slice still says DROP), but found 3
echo   confounded config differences between the two pipelines:
echo     1) --skip-counter-trend  (WFO has it, static sweep did not)
echo     2) spread $0.20 vs $0.13 (WFO vs static sweep default)
echo     3) joint drop (both features together) vs FS67-13's individual
echo        ablate-one-at-a-time
echo   This run matches ALL THREE to WFO's exact config, on a SINGLE
echo   train+backtest split (no weekly retrain) over the exact same H2
echo   window. If this run still says KEEP (matches FS67-22), the
echo   remaining difference -- retrain frequency -- is the real cause.
echo   If it says DROP (matches FS67-13), one of the 3 confounds above
echo   was the real cause, not retrain frequency.
echo.
echo %QGAI_CYAN%  Two arms:%QGAI_RESET%
echo   %QGAI_YELLOW%A) baseline_with_features%QGAI_RESET% -- QGAI_UNPRUNE=15_min_slot,M15_ADX
echo   %QGAI_YELLOW%B) candidate_live_dropped%QGAI_RESET%  -- no unprune (today's actual live)
echo.
echo   Train cutoff : %QGAI_TRAIN_CUTOFF%  (single retrain, NOT weekly WFO)
echo   Backtest     : 2025-12-29 to 2026-06-29  (same window as FS67-22)
echo   Flags        : --spread 0.20 --ratchet on --skip-counter-trend
echo                  --tp-regime --fixed-lot 0.01 --risk 3  (all match WFO)
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
echo %QGAI_GREEN%[1/4] Training ARM A - baseline_with_features...%QGAI_RESET%
set "QGAI_UNPRUNE=15_min_slot,M15_ADX"
set "QGAI_ABLATE="
"%PY%" train.py
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[2/4] Backtesting ARM A over H2 window...%QGAI_RESET%
"%PY%" backtest_replay.py --from 2025-12-29 --to 2026-06-29 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.15 --tp-equity-pct 0 --skip-counter-trend --tp-regime --fixed-lot 0.01 --max-open 1 --out-dir "%BASELINE_DIR%"
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[3/4] Training ARM B - candidate_live_dropped...%QGAI_RESET%
set "QGAI_UNPRUNE="
set "QGAI_ABLATE="
"%PY%" train.py
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[4/4] Backtesting ARM B over H2 window...%QGAI_RESET%
"%PY%" backtest_replay.py --from 2025-12-29 --to 2026-06-29 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.15 --tp-equity-pct 0 --skip-counter-trend --tp-regime --fixed-lot 0.01 --max-open 1 --out-dir "%CANDIDATE_DIR%"
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% DONE%QGAI_RESET%
echo ------------------------------------------------------------
echo   Baseline (with features)  : %BASELINE_DIR%\backtest_report.txt
echo   Candidate (live, dropped) : %CANDIDATE_DIR%\backtest_report.txt
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$baseSum='%BASELINE_DIR%\backtest_summary_st-htf.csv'; $candSum='%CANDIDATE_DIR%\backtest_summary_st-htf.csv';" ^
  "if((Test-Path $baseSum) -and (Test-Path $candSum)) {" ^
  "  $b=Import-Csv $baseSum; $c=Import-Csv $candSum;" ^
  "  $br=[double]$b[0].total_r; $cr=[double]$c[0].total_r;" ^
  "  Write-Host ''; Write-Host 'SINGLE-SPLIT H2 COMPARISON (retrain-frequency isolated)';" ^
  "  Write-Host ('With features (old)   : {0:N1}R' -f $br);" ^
  "  Write-Host ('Without features (live): {0:N1}R' -f $cr);" ^
  "  Write-Host ('Delta (live - old)     : {0:+0.0;-0.0;0.0}R' -f ($cr-$br));" ^
  "  Write-Host '';" ^
  "  Write-Host 'FS67-22 (weekly WFO)   found: with=+90.8R without=+75.6R delta=-15.2R';" ^
  "  Write-Host 'FS67-13 (static, full yr) found: dropping helped +5.9R/+6.8R (per feature, individual)';" ^
  "  Write-Host '';" ^
  "  Write-Host 'If this delta matches FS67-22''s sign (negative/live-worse) -> retrain frequency';" ^
  "  Write-Host 'is NOT the cause; the 3 confounds (skip-counter-trend/spread/joint-drop) were.';" ^
  "  Write-Host 'If this delta matches FS67-13''s sign (positive/live-better) -> retrain frequency';" ^
  "  Write-Host 'IS the remaining explanation. Run the full BACKTEST_RESULT_AUDIT.md checklist';" ^
  "  Write-Host 'before any KEEP/DROP/revert decision either way.';" ^
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
exit /b 1
