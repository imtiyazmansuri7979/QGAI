@echo off
setlocal
chcp 65001 >nul
title QGAI - Leakage Guard Smoke TEST

REM =====================================================================
REM  Imtiyaz spec 2026-07-13: prove the leakage guard actually blocks an
REM  overlapping backtest and actually allows a clean one, end-to-end -
REM  not just against synthetic unit-test data.
REM
REM  Steps:
REM    1. Unit tests (fast sanity gate)
REM    2. REAL retrain with QGAI_TRAIN_CUTOFF=2026-04-01 (core-only, fast).
REM       train.py's atomic swap backs up the CURRENT live models to
REM       data\models\final_prev automatically before swapping in the new
REM       ones - nothing is lost.
REM    3. backtest_replay.py --from 2026-03-25 --to 2026-04-10 - this window
REM       STARTS before the 2026-04-01 cutoff, so it overlaps training data
REM       - MUST be BLOCKED (non-zero exit) by the leakage guard.
REM    4. backtest_replay.py --from 2026-05-05 - starts well after cutoff
REM       - MUST PASS and actually run.
REM    5. Restore the ORIGINAL live models from final_prev - undo the test
REM       retrain, this bat must not leave the April-cutoff model live.
REM
REM  NOTE: no parentheses or exclamation marks inside any IF/ELSE block's
REM  echo text below - cmd.exe misparses them as block-structure characters
REM  and silently truncates or aborts the script (found the hard way).
REM
REM  WARNING: close the live bridge before running this - it retrains
REM  data\models\final, same as every other *_TEST.bat in this folder.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "MODELS=C:\QGAI\data\models\final"
set "MODELS_PREV=C:\QGAI\data\models\final_prev"
set "OUTBLOCK=C:\QGAI\backtest\results\leakage_smoke_SHOULD_BLOCK"
set "OUTPASS=C:\QGAI\backtest\results\leakage_smoke_SHOULD_PASS"

cd /d "%ROOT%\engine"

echo ============================================================
echo   LEAKAGE GUARD - SMOKE TEST
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [1/5] Unit tests...
"%PY%" -m unittest tests.test_leakage_guard
if errorlevel 1 goto UNITFAIL
echo   OK
goto STEP2

:UNITFAIL
echo *** UNIT TESTS FAILED - aborting, models untouched ***
pause
exit /b 1

:STEP2
echo.
echo [2/5] Retraining with QGAI_TRAIN_CUTOFF=2026-04-01 - core-only, fast...
echo   current live models auto-backed-up to %MODELS_PREV% by train.py's atomic swap
set "QGAI_TRAIN_CUTOFF=2026-04-01"
set "QGAI_CORE_ONLY=1"
"%PY%" train.py
set "TRAIN_RC=%ERRORLEVEL%"
set "QGAI_TRAIN_CUTOFF="
set "QGAI_CORE_ONLY="
if not "%TRAIN_RC%"=="0" goto TRAINFAIL
echo   OK
goto STEP3

:TRAINFAIL
echo *** TRAIN FAILED ***
pause
exit /b 1

:STEP3
echo.
echo [3/5] Backtest window 2026-03-25 to 2026-04-10 starts BEFORE cutoff - EXPECT BLOCK...
"%PY%" backtest_replay.py --from 2026-03-25 --to 2026-04-10 --equity 10000 --fixed-lot 0.01 --out-dir "%OUTBLOCK%"
if errorlevel 1 (
    set "STEP3_OK=1"
) else (
    set "STEP3_OK=0"
)
if "%STEP3_OK%"=="1" echo   PASS - correctly BLOCKED as expected
if "%STEP3_OK%"=="0" echo   FAIL - this backtest should have been BLOCKED but it ran

echo.
echo [4/5] Backtest window 2026-05-05 onward - well after cutoff - EXPECT PASS...
"%PY%" backtest_replay.py --from 2026-05-05 --to 2026-05-12 --equity 10000 --fixed-lot 0.01 --out-dir "%OUTPASS%"
if errorlevel 1 (
    set "STEP4_OK=0"
) else (
    set "STEP4_OK=1"
)
if "%STEP4_OK%"=="1" echo   PASS - correctly ran as expected
if "%STEP4_OK%"=="0" echo   FAIL - this clean backtest was blocked, guard is too strict

echo.
echo [5/5] Restoring ORIGINAL live models - undo the test retrain...
if exist "%MODELS_PREV%" (
    robocopy "%MODELS_PREV%" "%MODELS%" /MIR >nul
    echo   Restored live models from final_prev
) else (
    echo   WARNING: final_prev not found - live models are now the TEST April-cutoff version
    echo   Restore manually from git or your own backup before trusting live trading
)

echo.
echo ============================================================
echo   SMOKE TEST DONE
echo   Step 3 should BLOCK - result: %STEP3_OK%   1 equals pass, 0 equals fail
echo   Step 4 should PASS  - result: %STEP4_OK%   1 equals pass, 0 equals fail
echo   Results folder 1: %OUTBLOCK%
echo   Results folder 2: %OUTPASS%
echo ============================================================
pause
exit /b 0
