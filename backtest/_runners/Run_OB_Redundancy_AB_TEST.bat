@echo off
setlocal
chcp 65001 >nul
title QGAI - Order Block Redundancy Retrain A/B TEST

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_CTF_FADE=0"
set "TRAIN=C:\QGAI\engine\train.py"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "ARGS=--from 2026-04-01 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"
set "OUTBASE=C:\QGAI\backtest\results\ob_redundancy_RETRAIN_TEST"
set "MODELDIR=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\backups\OB_REDUNDANCY_PRE_%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "BACKUP=%BACKUP: =0%"

cd /d "%ROOT%\engine"

echo ============================================================
echo   ORDER BLOCK REDUNDANCY - RETRAIN A/B TEST
echo   IMPORTANT: each variant RETRAINS model with QGAI_ABLATE
echo   Old replay-only runner was invalid because saved model
echo   feature_names ignored FEATURE_COLS-only ablation.
echo.
echo   Period: 2026-04-01 to 2026-06-29
echo   Backup live model: %BACKUP%
echo   Results: %OUTBASE%
echo   %DATE% %TIME%
echo ============================================================
echo   WARNING: close live bridge before running this test.
echo   This script temporarily retrains data\models\final, then restores it.
echo ============================================================

if not exist "%MODELDIR%" (
    echo MODEL DIR NOT FOUND: %MODELDIR%
    pause
    exit /b 1
)

mkdir "%BACKUP%" >nul 2>nul
robocopy "%MODELDIR%" "%BACKUP%" /E >nul
if errorlevel 8 (
    echo BACKUP FAILED
    pause
    exit /b 1
)

call :RUN_ONE baseline ""
if errorlevel 1 goto FAIL
call :RUN_ONE D1_drop_h4_resist_dist "h4_resist_dist"
if errorlevel 1 goto FAIL
call :RUN_ONE D2_drop_h4_ob_strength "h4_ob_strength"
if errorlevel 1 goto FAIL
call :RUN_ONE D3_drop_h1_support_dist "h1_support_dist"
if errorlevel 1 goto FAIL
call :RUN_ONE D4_drop_h1_ob_strength "h1_ob_strength"
if errorlevel 1 goto FAIL
call :RUN_ONE D5_drop_h4resist_h4ob "h4_resist_dist,h4_ob_strength"
if errorlevel 1 goto FAIL
call :RUN_ONE D6_drop_h1support_h1ob "h1_support_dist,h1_ob_strength"
if errorlevel 1 goto FAIL

goto RESTORE_OK

:RUN_ONE
set "NAME=%~1"
set "DROP=%~2"
echo.
echo ------------------------------------------------------------
echo   [%NAME%]
if "%DROP%"=="" (
    echo   Features: baseline current model
    set "QGAI_ABLATE="
) else (
    echo   Dropping: %DROP%
    set "QGAI_ABLATE=%DROP%"
)
echo   Retraining...
"%PY%" "%TRAIN%"
if errorlevel 1 (
    echo TRAIN FAILED: %NAME%
    exit /b 1
)
echo   Replaying...
"%PY%" "%SCRIPT%" %ARGS% --out-dir "%OUTBASE%\%NAME%"
if errorlevel 1 (
    echo BACKTEST FAILED: %NAME%
    exit /b 1
)
exit /b 0

:FAIL
echo.
echo ============================================================
echo   FAILED - restoring original live model from backup
echo ============================================================
set "QGAI_ABLATE="
robocopy "%BACKUP%" "%MODELDIR%" /MIR >nul
if errorlevel 8 echo WARNING: RESTORE FAILED - check %BACKUP%
pause
exit /b 1

:RESTORE_OK
echo.
echo ============================================================
echo   TEST DONE - restoring original live model
echo ============================================================
set "QGAI_ABLATE="
robocopy "%BACKUP%" "%MODELDIR%" /MIR >nul
if errorlevel 8 (
    echo RESTORE FAILED - check backup: %BACKUP%
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   DONE - %DATE% %TIME%
echo   Results in: %OUTBASE%\
echo.
echo   Rule:
echo     Drop model >= baseline R = candidate redundant
echo     Drop model < baseline R  = keep feature
echo.
echo   NOTE:
echo     This is retrain-based TEST. For final prune, confirm with WFO.
echo ============================================================
pause
exit /b 0
