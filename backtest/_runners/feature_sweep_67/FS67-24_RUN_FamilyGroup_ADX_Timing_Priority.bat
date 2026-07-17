@echo off
setlocal
chcp 65001 >nul
call "%~dp0..\_console_theme.bat"
title QGAI - FS67-24 - Restore-Value Test: Dropped Timing + ADX_DI members

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-24"
set "RESULT_BASE=C:\QGAI\backtest\results\FS67-24_family_group"
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"
set "QGAI_TRAIN_CUTOFF=2025-12-28"

set "BT_FROM=2025-12-29"
set "BT_TO=2026-06-29"
set "BT_FLAGS=--equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.15 --tp-equity-pct 0 --tp-regime --fixed-lot 0.01 --max-open 1"

cd /d "%ROOT%\engine"

echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% - Restore-Value Test (revised 2026-07-17)%QGAI_RESET%
echo %QGAI_DIM%------------------------------------------------------------%QGAI_RESET%
echo.
echo   REVISED per Imtiyaz's objection (2026-07-17): the original design
echo   (ablate WHOLE family) was dropped. Removing 7-11 correlated active
echo   features at once is a trivial test -- it will ALWAYS show a big
echo   loss (that's not evidence of a specific pairwise interaction, just
echo   proof the family carries signal, which was never in question).
echo   Fable-5 confirmed this critique. Whole-family ABLATE arms removed.
echo.
echo   What THIS run still answers (kept, still decision-relevant):
echo   "should any of the currently-DROPPED Timing/ADX_DI members come
echo   back?" -- a real restore-value question, same logic as FS67-13.
echo   15_min_slot + M15_ADX interaction is ALREADY PROVEN by FS67-22/23
echo   (-20.7R jointly) -- not re-tested here.
echo.
echo %QGAI_CYAN%  3 Arms (1 baseline + 2 restore tests):%QGAI_RESET%
echo   %QGAI_YELLOW%A) baseline%QGAI_RESET%           -- current live model (25 features, both dropped)
echo   %QGAI_YELLOW%D) unprune_timing%QGAI_RESET%     -- RESTORE dropped Timing (15_min_slot, session_score, is_ny_session, is_dead_hour)
echo   %QGAI_YELLOW%E) unprune_adx_di%QGAI_RESET%     -- RESTORE dropped ADX_DI (M15_ADX, M30_ADX, H1_ADX, adx_trend_count)
echo.
echo   Train cutoff : %QGAI_TRAIN_CUTOFF%
echo   Backtest     : %BT_FROM% to %BT_TO%  (same H2 window as FS67-22/23)
echo   Spread       : $0.20 (WFO-matching)
echo.
echo   For the interaction QUESTION (are there OTHER hidden pairs we
echo   missed?), see FS67-25 (SHAP interaction screen, zero-retrain) and
echo   FS67-27 (cumulative joint-drop of the full pruned set).
echo.
echo   All retrains in data\models\test_workspace. Live model NOT touched.
echo.
echo   %QGAI_YELLOW%Estimated time: ~1.5 hours (3 arms x ~27 min each: train ~12m + BT ~15m)%QGAI_RESET%
echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%

if exist "C:\QGAI\data\models\.training_lock" (
  echo.
  echo %QGAI_RED%%QGAI_BOLD%FAILED %RUN_ID%%QGAI_RESET%
  echo Training lock exists. Delete if no train.py running.
  pause
  exit /b 1
)

set "STEPS_TOTAL=6"
set "STEP=0"

REM ═══════════════════════════════════════════════════════
REM ARM A — BASELINE (current live, no changes)
REM ═══════════════════════════════════════════════════════
set /a STEP+=1
echo.
echo %QGAI_GREEN%[%STEP%/%STEPS_TOTAL%] Training ARM A - baseline...%QGAI_RESET%
set "QGAI_ABLATE="
set "QGAI_UNPRUNE="
"%PY%" train.py
if errorlevel 1 goto fail

set /a STEP+=1
echo.
echo %QGAI_GREEN%[%STEP%/%STEPS_TOTAL%] Backtesting ARM A - baseline...%QGAI_RESET%
"%PY%" backtest_replay.py --from %BT_FROM% --to %BT_TO% %BT_FLAGS% --out-dir "%RESULT_BASE%\A_baseline"
if errorlevel 1 goto fail

REM ═══════════════════════════════════════════════════════
REM ARM D — UNPRUNE Timing dropped (restore value test)
REM   15_min_slot, session_score, is_ny_session, is_dead_hour
REM ═══════════════════════════════════════════════════════
set /a STEP+=1
echo.
echo %QGAI_GREEN%[%STEP%/%STEPS_TOTAL%] Training ARM D - unprune Timing (4 features)...%QGAI_RESET%
set "QGAI_ABLATE="
set "QGAI_UNPRUNE=15_min_slot,session_score,is_ny_session,is_dead_hour"
"%PY%" train.py
if errorlevel 1 goto fail

set /a STEP+=1
echo.
echo %QGAI_GREEN%[%STEP%/%STEPS_TOTAL%] Backtesting ARM D - unprune Timing...%QGAI_RESET%
"%PY%" backtest_replay.py --from %BT_FROM% --to %BT_TO% %BT_FLAGS% --out-dir "%RESULT_BASE%\D_unprune_timing"
if errorlevel 1 goto fail

REM ═══════════════════════════════════════════════════════
REM ARM E — UNPRUNE ADX_DI dropped (restore value test)
REM   M15_ADX, M30_ADX, H1_ADX, adx_trend_count
REM ═══════════════════════════════════════════════════════
set /a STEP+=1
echo.
echo %QGAI_GREEN%[%STEP%/%STEPS_TOTAL%] Training ARM E - unprune ADX_DI (4 features)...%QGAI_RESET%
set "QGAI_ABLATE="
set "QGAI_UNPRUNE=M15_ADX,M30_ADX,H1_ADX,adx_trend_count"
"%PY%" train.py
if errorlevel 1 goto fail

set /a STEP+=1
echo.
echo %QGAI_GREEN%[%STEP%/%STEPS_TOTAL%] Backtesting ARM E - unprune ADX_DI...%QGAI_RESET%
"%PY%" backtest_replay.py --from %BT_FROM% --to %BT_TO% %BT_FLAGS% --out-dir "%RESULT_BASE%\E_unprune_adx_di"
if errorlevel 1 goto fail

REM ═══════════════════════════════════════════════════════
REM COMPARISON
REM ═══════════════════════════════════════════════════════
echo.
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% DONE — All 3 arms complete%QGAI_RESET%
echo ------------------------------------------------------------%QGAI_RESET%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$arms = @(" ^
  "  @{name='A_baseline';         label='Baseline (current live)'}," ^
  "  @{name='D_unprune_timing';   label='UNPRUNE Timing (+4 dropped)'}," ^
  "  @{name='E_unprune_adx_di';   label='UNPRUNE ADX_DI (+4 dropped)'}" ^
  ");" ^
  "$base='%RESULT_BASE%';" ^
  "$baseR = $null;" ^
  "Write-Host '';" ^
  "Write-Host '  FS67-24 RESTORE-VALUE COMPARISON' -ForegroundColor Cyan;" ^
  "Write-Host '  ════════════════════════════════════════════════════════' -ForegroundColor DarkGray;" ^
  "Write-Host ('  {0,-35} {1,8} {2,7} {3,6} {4,10}' -f 'Arm','Total_R','Trades','WR%','Delta');" ^
  "Write-Host '  ────────────────────────────────────────────────────────' -ForegroundColor DarkGray;" ^
  "foreach ($a in $arms) {" ^
  "  $csv = Join-Path $base ($a.name + '\backtest_summary_st-htf.csv');" ^
  "  if (Test-Path $csv) {" ^
  "    $d = Import-Csv $csv;" ^
  "    $r = [double]$d[0].total_r; $t = $d[0].trades; $w = $d[0].wr;" ^
  "    if ($null -eq $baseR) { $baseR = $r };" ^
  "    $delta = $r - $baseR;" ^
  "    $deltaStr = if ($a.name -eq 'A_baseline') { '   ---' } else { '{0:+0.0;-0.0;0.0}R' -f $delta };" ^
  "    Write-Host ('  {0,-35} {1,7:N1}R {2,7} {3,5:N1}%% {4,10}' -f $a.label,$r,$t,$w,$deltaStr);" ^
  "  } else { Write-Host ('  {0,-35} CSV missing' -f $a.label) -ForegroundColor Red }" ^
  "};" ^
  "Write-Host '  ════════════════════════════════════════════════════════' -ForegroundColor DarkGray;" ^
  "Write-Host '';" ^
  "Write-Host '  Reading guide:' -ForegroundColor Yellow;" ^
  "Write-Host '    D positive delta = dropped Timing members should come back (needs OOS confirm)';" ^
  "Write-Host '    E positive delta = dropped ADX_DI members should come back (needs OOS confirm)';" ^
  "Write-Host '    (delta must exceed FS67-26 noise floor to be trustworthy)';" ^
  "Write-Host ''"

echo.
echo   Result folders:
echo     %RESULT_BASE%\A_baseline
echo     %RESULT_BASE%\D_unprune_timing
echo     %RESULT_BASE%\E_unprune_adx_di
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%

pause
exit /b 0

:fail
echo.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_RED%%QGAI_BOLD%  FAILED %RUN_ID% at step %STEP%/%STEPS_TOTAL%%QGAI_RESET%
echo   Check output above for error details.
echo   Resume-safe: completed arms are cached in result folders.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
pause
exit /b 1
