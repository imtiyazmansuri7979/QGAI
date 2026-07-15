@echo off
setlocal
chcp 65001 >nul
title QGAI - FS67-21 - h4_support_dist WFO 6M

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_ID=FS67-21"
set "RESULT_ID=FS67-21_h4_support_wfo6m_20251229_20260629"
set "BASELINE_DIR=C:\QGAI\backtest\results\wfo_current_live_28feat_20260714"
set "CANDIDATE_DIR=C:\QGAI\backtest\results\%RESULT_ID%"

REM Candidate only: add back h4_support_dist for this WFO.
set "QGAI_UNPRUNE=h4_support_dist"
set "QGAI_ABLATE="
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"

cd /d "%ROOT%\engine"

echo ============================================================
echo   %RUN_ID% - h4_support_dist - 6M WFO
echo ------------------------------------------------------------
echo   Candidate:
echo     QGAI_UNPRUNE=%QGAI_UNPRUNE%
echo.
echo   Period:
echo     2025-12-29 to 2026-06-29  (~6 months / weekly WFO)
echo.
echo   Baseline is NOT rerun.
echo   Compare against existing:
echo     %BASELINE_DIR%\_WFO_SUMMARY.csv
echo.
echo   Candidate result:
echo     %CANDIDATE_DIR%
echo.
echo   Live model is NOT touched.
echo.
echo   Instructions:
echo   - Candidate-only WFO: baseline is NOT rerun.
echo   - Compare against existing current-model WFO summary for same weeks.
echo   - If training lock exists, check for train.py/backtest_replay.py first.
echo   - This is extra due diligence because OOS1Y already rejected the feature.
echo ============================================================

if exist "C:\QGAI\data\models\.training_lock" (
  echo.
  echo FAILED %RUN_ID%
  echo Training lock exists:
  echo   C:\QGAI\data\models\.training_lock
  echo If no train.py is running, delete the lock and rerun.
  pause
  exit /b 1
)

"%PY%" run_wfo.py --start 2025-12-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir %RESULT_ID%
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto fail

echo.
echo ============================================================
echo   %RUN_ID% DONE
echo ------------------------------------------------------------
echo   Candidate summary:
echo     %CANDIDATE_DIR%\_WFO_SUMMARY.csv
echo.
echo   Baseline summary:
echo     %BASELINE_DIR%\_WFO_SUMMARY.csv
echo.
echo   Compare same weeks only:
echo     baseline current model vs candidate h4_support_dist
echo ============================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$base='%BASELINE_DIR%\_WFO_SUMMARY.csv'; $cand='%CANDIDATE_DIR%\_WFO_SUMMARY.csv';" ^
  "if((Test-Path $base) -and (Test-Path $cand)) {" ^
  "  $b=Import-Csv $base | ? { $_.week_start -match '^\d{4}-\d{2}-\d{2}$' -and [datetime]$_.week_start -ge [datetime]'2025-12-29' -and [datetime]$_.week_start -lt [datetime]'2026-06-29' };" ^
  "  $c=Import-Csv $cand | ? { $_.week_start -match '^\d{4}-\d{2}-\d{2}$' };" ^
  "  $br=($b | Measure-Object total_r -Sum).Sum; $cr=($c | Measure-Object total_r -Sum).Sum;" ^
  "  $bt=($b | Measure-Object trades -Sum).Sum; $ct=($c | Measure-Object trades -Sum).Sum;" ^
  "  $bp=($b | ? { [double]$_.total_r -gt 0 }).Count; $cp=($c | ? { [double]$_.total_r -gt 0 }).Count;" ^
  "  Write-Host ''; Write-Host 'WFO6M COMPARISON';" ^
  "  Write-Host ('Baseline R : {0:N1}R | trades {1} | positive weeks {2}/{3}' -f $br,$bt,$bp,$b.Count);" ^
  "  Write-Host ('Candidate R: {0:N1}R | trades {1} | positive weeks {2}/{3}' -f $cr,$ct,$cp,$c.Count);" ^
  "  Write-Host ('Delta     : {0:+0.0;-0.0;0.0}R' -f ($cr-$br));" ^
  "} else { Write-Host 'Compare skipped: baseline or candidate summary missing.' }"

pause
exit /b 0

:fail
echo.
echo ============================================================
echo   FAILED %RUN_ID%
echo   Check:
echo     %CANDIDATE_DIR%
echo ============================================================
pause
exit /b %RC%
