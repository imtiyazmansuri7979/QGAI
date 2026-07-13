@echo off
setlocal
chcp 65001 >nul
title QGAI - Removed Feature 11 Candidate Retrain TEST

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
set "MODELDIR=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\backups\REMOVED_FEATURE_10_PRE_%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "BACKUP=%BACKUP: =0%"

cd /d "%ROOT%\engine"

echo ============================================================
echo   REMOVED FEATURE 11 CANDIDATE - RETRAIN + 3-MONTH TEST
echo ------------------------------------------------------------
echo   Baseline = current 27-feature code model.
echo   Each candidate temporarily restores ONE removed feature via
echo   QGAI_UNPRUNE, retrains, then replays 2026-04-01 to 2026-06-29.
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
robocopy "%MODELDIR%" "%BACKUP%" /E >nul
if errorlevel 8 (
    echo BACKUP FAILED
    pause
    exit /b 1
)

call :RUN_ONE baseline ""
if errorlevel 1 goto FAIL
call :RUN_ONE A01_plus_h4_support_dist "h4_support_dist"
if errorlevel 1 goto FAIL
call :RUN_ONE A02_plus_h1_resist_dist "h1_resist_dist"
if errorlevel 1 goto FAIL
call :RUN_ONE A03_plus_move_2hr "move_2hr"
if errorlevel 1 goto FAIL
call :RUN_ONE A04_plus_ts_line_dist_pct "ts_line_dist_pct"
if errorlevel 1 goto FAIL
call :RUN_ONE A05_plus_ts_trend_m15 "ts_trend_m15"
if errorlevel 1 goto FAIL
call :RUN_ONE A06_plus_ts_trend_h4 "ts_trend_h4"
if errorlevel 1 goto FAIL
call :RUN_ONE A07_plus_is_post_news "is_post_news"
if errorlevel 1 goto FAIL
call :RUN_ONE A08_plus_is_dead_hour "is_dead_hour"
if errorlevel 1 goto FAIL
call :RUN_ONE A09_plus_tick_volume "tick_volume"
if errorlevel 1 goto FAIL
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
if "%ADD%"=="" (
    echo   Candidate: current 27-feature baseline
    set "QGAI_UNPRUNE="
) else (
    echo   Candidate: restore %ADD%
    set "QGAI_UNPRUNE=%ADD%"
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
echo     %OUTBASE%
echo.
echo   Rule:
echo     Candidate R greater than baseline = possible restore candidate.
echo     Final adoption still needs WFO gate.
echo ============================================================
pause
exit /b 0
