@echo off
setlocal
chcp 65001 >nul
title QGAI - PART 1: Drop 6 dead features -> Retrain -> WFO gate

REM =====================================================================
REM  PART 1 (Imtiyaz 2026-07-07): 6 dead EA-threshold-combo features
REM  dropped from features.py (_MANUAL_PRUNE). This bat:
REM    1. BACKS UP current models  (so revert is trivial)
REM    2. RETRAINS on the 35-feature set (merge_data + train)
REM    3. WFO over the live period, compares vs +393.7R honest baseline
REM
REM  DECISION RULE: adopt ONLY if WFO total R >= +393.7R (>= baseline).
REM  If it drops -> restore backup, delete the 6 prune lines in features.py.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "MODELS=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\_backup_pre_part1_prune"

cd /d "%ROOT%\engine"

echo ============================================================
echo PART 1 — prune 6 dead features, retrain, WFO   %DATE% %TIME%
echo ============================================================

REM ---------- 1. BACKUP current models ----------
if exist "%BACKUP%" (
  echo Backup already exists at %BACKUP% - skipping backup ^(keep original^).
) else (
  echo Backing up current models -^> %BACKUP%
  xcopy /E /I /Y "%MODELS%" "%BACKUP%" >nul
  if errorlevel 1 goto fail
)
echo.

REM ---------- 2. RETRAIN ----------
echo [2/3] Merging data...
"%PY%" merge_data.py
if errorlevel 1 ( echo Data merge FAILED. & goto fail )
echo [2/3] Training models on 35-feature set...
"%PY%" train.py
if errorlevel 1 ( echo Training FAILED. & goto fail )
echo.

REM ---------- 3. WFO gate ----------
echo [3/3] WFO over live period (2025-06-29 -^> 2026-06-29)...
"%PY%" run_wfo.py --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --results-dir wfo_part1_prune35
if errorlevel 1 goto fail

echo.
echo ============================================================
echo PART 1 DONE %DATE% %TIME%
echo Compare WFO total R vs baseline +393.7R:
echo   results: C:\QGAI\backtest\results\wfo_part1_prune35\  (_WFO_SUMMARY.csv)
echo ADOPT if  >= +393.7R.  If LOWER:
echo   xcopy /E /I /Y "%BACKUP%" "%MODELS%"   ^(restore^)
echo   then delete the 6 PART 1 lines in engine/features.py _MANUAL_PRUNE.
echo ============================================================
pause
exit /b 0

:fail
echo.
echo *** PART 1 FAILED %DATE% %TIME% — models NOT changed if before train.
echo *** If training ran, restore:  xcopy /E /I /Y "%BACKUP%" "%MODELS%"
pause
exit /b 1
