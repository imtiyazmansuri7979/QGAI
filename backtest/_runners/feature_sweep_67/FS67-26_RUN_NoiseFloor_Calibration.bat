@echo off
setlocal
chcp 65001 >nul
call "%~dp0..\_console_theme.bat"
title QGAI - FS67-26 - Noise Floor Calibration (3 seeds, same features)

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-26"
set "RESULT_BASE=C:\QGAI\backtest\results\FS67-26_noise_floor"
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"
set "QGAI_TRAIN_CUTOFF=2025-12-28"

set "BT_FROM=2025-12-29"
set "BT_TO=2026-06-29"
set "BT_FLAGS=--equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.15 --tp-equity-pct 0 --tp-regime --fixed-lot 0.01 --max-open 1"

cd /d "%ROOT%\engine"

echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% - Noise Floor Calibration%QGAI_RESET%
echo %QGAI_DIM%------------------------------------------------------------%QGAI_RESET%
echo.
echo   Purpose (Fable-5, 2026-07-17): NO feature-sweep delta has ever been
echo   compared against how much total_R varies just from RANDOM SEED,
echo   with the feature set held IDENTICAL. Any KEEP/DROP delta smaller
echo   than this noise floor is not trustworthy.
echo.
echo   Retrains the SAME current-live feature set 3 times with different
echo   random seeds (QGAI_SEED, new env var added to xgb_model.py
echo   2026-07-17), same window/config as FS67-22/23/24. The SPREAD of
echo   total_R across these 3 identical-feature runs = the noise floor.
echo   Any FS67-24/27 delta smaller than this spread should be treated
echo   as "no real difference detected", not KEEP or DROP.
echo.
echo   Train cutoff : %QGAI_TRAIN_CUTOFF%
echo   Backtest     : %BT_FROM% to %BT_TO%  (same H2 window as FS67-22/23/24)
echo   Seeds        : 42 (original), 43, 44
echo.
echo   All retrains in data\models\test_workspace. Live model NOT touched.
echo.
echo   %QGAI_YELLOW%Estimated time: ~1.5 hours (3 seeds x ~27 min each: train ~12m + BT ~15m)%QGAI_RESET%
echo %QGAI_CYAN%%QGAI_BOLD%============================================================%QGAI_RESET%

if exist "C:\QGAI\data\models\.training_lock" (
  echo.
  echo %QGAI_RED%%QGAI_BOLD%FAILED %RUN_ID%%QGAI_RESET%
  echo Training lock exists. Delete if no train.py running.
  pause
  exit /b 1
)

set "QGAI_ABLATE="
set "QGAI_UNPRUNE="

echo.
echo %QGAI_GREEN%[1/6] Training seed=42...%QGAI_RESET%
set "QGAI_SEED=42"
"%PY%" train.py
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[2/6] Backtesting seed=42...%QGAI_RESET%
"%PY%" backtest_replay.py --from %BT_FROM% --to %BT_TO% %BT_FLAGS% --out-dir "%RESULT_BASE%\seed_42"
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[3/6] Training seed=43...%QGAI_RESET%
set "QGAI_SEED=43"
"%PY%" train.py
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[4/6] Backtesting seed=43...%QGAI_RESET%
"%PY%" backtest_replay.py --from %BT_FROM% --to %BT_TO% %BT_FLAGS% --out-dir "%RESULT_BASE%\seed_43"
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[5/6] Training seed=44...%QGAI_RESET%
set "QGAI_SEED=44"
"%PY%" train.py
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%[6/6] Backtesting seed=44...%QGAI_RESET%
"%PY%" backtest_replay.py --from %BT_FROM% --to %BT_TO% %BT_FLAGS% --out-dir "%RESULT_BASE%\seed_44"
if errorlevel 1 goto fail

echo.
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_GREEN%%QGAI_BOLD%  %RUN_ID% DONE — 3 seeds complete%QGAI_RESET%
echo ------------------------------------------------------------%QGAI_RESET%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$seeds = @('seed_42','seed_43','seed_44');" ^
  "$base='%RESULT_BASE%';" ^
  "$vals = @();" ^
  "Write-Host '';" ^
  "Write-Host '  FS67-26 NOISE FLOOR' -ForegroundColor Cyan;" ^
  "Write-Host '  ══════════════════════════════════════' -ForegroundColor DarkGray;" ^
  "foreach ($s in $seeds) {" ^
  "  $csv = Join-Path $base ($s + '\backtest_summary_st-htf.csv');" ^
  "  if (Test-Path $csv) {" ^
  "    $d = Import-Csv $csv; $r = [double]$d[0].total_r; $vals += $r;" ^
  "    Write-Host ('  {0,-12} {1,8:N1}R' -f $s,$r);" ^
  "  } else { Write-Host ('  {0,-12} CSV missing' -f $s) -ForegroundColor Red }" ^
  "};" ^
  "if ($vals.Count -ge 2) {" ^
  "  $spread = ($vals | Measure-Object -Maximum -Minimum);" ^
  "  $range = $spread.Maximum - $spread.Minimum;" ^
  "  $mean = ($vals | Measure-Object -Average).Average;" ^
  "  Write-Host '  ──────────────────────────────────────' -ForegroundColor DarkGray;" ^
  "  Write-Host ('  Mean: {0:N1}R | Range (max-min): {1:N1}R' -f $mean,$range) -ForegroundColor Yellow;" ^
  "  Write-Host '';" ^
  "  Write-Host ('  NOISE FLOOR = {0:N1}R' -f $range) -ForegroundColor Green;" ^
  "  Write-Host '  Any KEEP/DROP delta from FS67-24/27 smaller than this is NOT trustworthy.';" ^
  "};" ^
  "Write-Host ''"

echo.
echo   Result folders:
echo     %RESULT_BASE%\seed_42
echo     %RESULT_BASE%\seed_43
echo     %RESULT_BASE%\seed_44
echo %QGAI_GREEN%%QGAI_BOLD%============================================================%QGAI_RESET%

pause
exit /b 0

:fail
echo.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
echo %QGAI_RED%%QGAI_BOLD%  FAILED %RUN_ID%%QGAI_RESET%
echo   Check output above for error details.
echo   Resume-safe: completed seeds are cached in result folders.
echo %QGAI_RED%%QGAI_BOLD%============================================================%QGAI_RESET%
pause
exit /b 1
