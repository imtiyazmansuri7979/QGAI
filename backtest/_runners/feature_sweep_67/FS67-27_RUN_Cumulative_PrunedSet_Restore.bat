@echo off
setlocal
chcp 65001 >nul
call "%~dp0..\_console_theme.bat"
title QGAI - FS67-27 - Cumulative Restore: ALL 32 performance-pruned features

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-27"
set "RESULT_BASE=C:\QGAI\backtest\results\FS67-27_cumulative_restore"
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"
set "QGAI_TRAIN_CUTOFF=2025-12-28"

set "BT_FROM=2025-12-29"
set "BT_TO=2026-06-29"
set "BT_FLAGS=--equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.15 --tp-equity-pct 0 --tp-regime --fixed-lot 0.01 --max-open 1"

REM All 32 restorable _MANUAL_PRUNE features (corr_imp_ratio EXCLUDED —
REM its computation was deleted 2026-07-16, QGAI_UNPRUNE is a no-op for it).
REM Includes policy drops (ts_line_dist_pct, volume/tick_volume, EMA200
REM extras) alongside performance drops -- this is the FULL cumulative
REM test. If delta is large, Step 2 (bisection) narrows down which half
REM is responsible; policy drops may stay dropped regardless of backtest
REM result (Anisa's explicit request), but need to be known either way.
set "RESTORE_SET=15_min_slot,H1_ADX,M15_ADX,M30_ADX,above_ema200,adx_trend_count,ema200_dist_abs,h1_in_ob_zone,h1_ob_strength,h1_resist_dist,h1_support_dist,h4_in_ob_zone,h4_ob_strength,h4_ranging_h1_extended,h4_ranging_h1_neutral,h4_resist_dist,h4_support_dist,h4_trending_h1_aligned,is_ny_session,is_post_big_move,last_3star_dev_sign,move_2hr,move_8hr,near_ema200,session_score,tick_volume,trade_direction,ts_adx_switch_trend,ts_line_dist_pct,ts_trend_h1,upcoming_3star_count,volume"

cd /d "%ROOT%\engine"

echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% - Cumulative Restore Test (Fable-5 Step 1)%QGAI_RESET%
echo %QGAI_DIM%------------------------------------------------------------%QGAI_RESET%
echo.
echo   Purpose: every one of the 32 _MANUAL_PRUNE features was validated
echo   INDIVIDUALLY, one at a time, never jointly (same flaw that caused
echo   the 15_min_slot+M15_ADX -20.7R surprise, at cumulative scale).
echo   This tests the actual SHIPPED decision directly: does restoring
echo   ALL 32 together beat the current live (25-feature) model?
echo.
echo   If YES (Arm F beats baseline by more than FS67-26's noise floor):
echo   cumulative individual-only pruning cost real R -- proceed to
echo   bisection (split the 32 in half, retest each half, recurse on
echo   whichever half is responsible) to isolate the culprit subset.
echo.
echo   If NO (delta within noise floor, or negative): the individual
echo   pruning decisions were, in aggregate, fine -- no further
echo   cumulative testing needed. The 15_min_slot+M15_ADX pair remains
echo   the one confirmed exception (already handled separately).
echo.
echo %QGAI_CYAN%  2 Arms:%QGAI_RESET%
echo   %QGAI_YELLOW%A) baseline%QGAI_RESET%  -- current live model (25 features)
echo   %QGAI_YELLOW%F) full_restore%QGAI_RESET%  -- all 32 restorable pruned features added back (57 total)
echo.
echo   Train cutoff : %QGAI_TRAIN_CUTOFF%
echo   Backtest     : %BT_FROM% to %BT_TO%  (same H2 window as FS67-22/23/24/26)
echo.
echo   All retrains in data\models\test_workspace. Live model NOT touched.
echo.
echo   %QGAI_YELLOW%Estimated time: ~1 hour (2 arms x ~27 min each: train ~12m + BT ~15m)%QGAI_RESET%
echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%

if exist "C:\QGAI\data\models\.training_lock" (
  echo.
  echo %QGAI_RED%%QGAI_BOLD%FAILED %RUN_ID%%QGAI_RESET%
  echo Training lock exists. Delete if no train.py running.
  pause
  exit /b 1
)

echo.
echo %QGAI_GREEN%[1/4] Training ARM A - baseline...%QGAI_RESET%
set "QGAI_ABLATE="
set "QGAI_UNPRUNE="
"%PY%" train.py
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[2/4] Backtesting ARM A - baseline...%QGAI_RESET%
"%PY%" backtest_replay.py --from %BT_FROM% --to %BT_TO% %BT_FLAGS% --out-dir "%RESULT_BASE%\A_baseline"
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[3/4] Training ARM F - full restore (32 features)...%QGAI_RESET%
set "QGAI_ABLATE="
set "QGAI_UNPRUNE=%RESTORE_SET%"
"%PY%" train.py
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[4/4] Backtesting ARM F - full restore...%QGAI_RESET%
"%PY%" backtest_replay.py --from %BT_FROM% --to %BT_TO% %BT_FLAGS% --out-dir "%RESULT_BASE%\F_full_restore"
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% DONE%QGAI_RESET%
echo ------------------------------------------------------------%QGAI_RESET%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$baseSum='%RESULT_BASE%\A_baseline\backtest_summary_st-htf.csv';" ^
  "$fullSum='%RESULT_BASE%\F_full_restore\backtest_summary_st-htf.csv';" ^
  "if((Test-Path $baseSum) -and (Test-Path $fullSum)) {" ^
  "  $b=Import-Csv $baseSum; $f=Import-Csv $fullSum;" ^
  "  $br=[double]$b[0].total_r; $fr=[double]$f[0].total_r;" ^
  "  Write-Host ''; Write-Host '  FS67-27 CUMULATIVE RESTORE COMPARISON' -ForegroundColor Cyan;" ^
  "  Write-Host ('  Baseline (live, 25 feat)      : {0:N1}R' -f $br);" ^
  "  Write-Host ('  Full restore (57 feat)        : {0:N1}R' -f $fr);" ^
  "  Write-Host ('  Delta (restore - baseline)    : {0:+0.0;-0.0;0.0}R' -f ($fr-$br));" ^
  "  Write-Host '';" ^
  "  Write-Host '  Compare this delta against FS67-26''s noise floor before deciding.';" ^
  "  Write-Host '  If |delta| > noise floor and positive -> proceed to bisection.';" ^
  "  Write-Host '  If |delta| <= noise floor -> individual pruning was fine in aggregate.';" ^
  "} else { Write-Host 'Compare skipped: baseline or full_restore summary missing.' }"

echo.
echo   Result folders:
echo     %RESULT_BASE%\A_baseline
echo     %RESULT_BASE%\F_full_restore
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%

pause
exit /b 0

:fail
echo.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_RED%%QGAI_BOLD%  FAILED %RUN_ID%%QGAI_RESET%
echo   Check output above for error details.
echo   Resume-safe: completed arms are cached in result folders.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
pause
exit /b 1
