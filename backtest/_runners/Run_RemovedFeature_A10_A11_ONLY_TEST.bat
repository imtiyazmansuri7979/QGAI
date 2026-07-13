@echo off
setlocal
chcp 65001 >nul
title QGAI - Removed Feature A10 A11 Only TEST

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_CTF_FADE=0"
set "QGAI_ABLATE="
set "TRAIN=C:\QGAI\engine\train.py"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "ARGS=--from 2026-04-01 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"
set "OUTBASE=C:\QGAI\backtest\results\removed_feature_10_RETRAIN_TEST"
set "LOGDIR=C:\QGAI\backtest\results\removed_feature_10_RETRAIN_TEST\_logs_A10_A11"
set "MODELDIR=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\backups\REMOVED_FEATURE_A10_A11_PRE_%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "BACKUP=%BACKUP: =0%"

cd /d "%ROOT%\engine"

echo ============================================================
echo   REMOVED FEATURE A10/A11 ONLY - RETRAIN + 3-MONTH TEST
echo ------------------------------------------------------------
echo   Runs only:
echo     A10_plus_near_ema200
echo     A11_plus_volume_norm
echo.
echo   WARNING: close live bridge before running.
echo   This script temporarily retrains data\models\final, then restores it.
echo ============================================================

if not exist "%MODELDIR%" (
    echo MODEL DIR NOT FOUND: %MODELDIR%
    pause
    exit /b 1
)

mkdir "%BACKUP%" >nul 2>nul
mkdir "%LOGDIR%" >nul 2>nul
robocopy "%MODELDIR%" "%BACKUP%" /E >nul
if errorlevel 8 (
    echo BACKUP FAILED
    pause
    exit /b 1
)

call :RUN_ONE A10_plus_near_ema200 "near_ema200"
if errorlevel 1 goto FAIL
call :RUN_ONE A11_plus_volume_norm "volume"
if errorlevel 1 goto FAIL

goto RESTORE_OK

:RUN_ONE
set "NAME=%~1"
set "ADD=%~2"
echo.
echo ------------------------------------------------------------
echo   [%NAME%]
echo   Candidate: restore %ADD%
set "QGAI_UNPRUNE=%ADD%"
echo   Retraining...
"%PY%" "%TRAIN%" > "%LOGDIR%\%NAME%_train.log" 2>&1
if errorlevel 1 (
    echo TRAIN FAILED: %NAME%
    echo See log: "%LOGDIR%\%NAME%_train.log"
    exit /b 1
)
echo   Replaying...
"%PY%" "%SCRIPT%" %ARGS% --out-dir "%OUTBASE%\%NAME%" > "%LOGDIR%\%NAME%_backtest.log" 2>&1
if errorlevel 1 (
    echo BACKTEST FAILED: %NAME%
    echo See log: "%LOGDIR%\%NAME%_backtest.log"
    exit /b 1
)
exit /b 0

:FAIL
echo.
echo ============================================================
echo   FAILED - restoring original live model
echo ============================================================
set "QGAI_UNPRUNE="
set "QGAI_ABLATE="
robocopy "%BACKUP%" "%MODELDIR%" /MIR >nul
if errorlevel 8 echo WARNING: RESTORE FAILED - check backup: %BACKUP%
pause
exit /b 1

:RESTORE_OK
echo.
echo ============================================================
echo   TEST DONE - restoring original live model
echo ============================================================
set "QGAI_UNPRUNE="
set "QGAI_ABLATE="
robocopy "%BACKUP%" "%MODELDIR%" /MIR >nul
if errorlevel 8 (
    echo RESTORE FAILED - check backup: %BACKUP%
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   DONE
echo   Results in:
echo     %OUTBASE%\A10_plus_near_ema200
echo     %OUTBASE%\A11_plus_volume_norm
echo ============================================================
pause
exit /b 0
