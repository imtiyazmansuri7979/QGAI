@echo off
setlocal
chcp 65001 >nul
title QGAI - Top 5 Removed Features Cumulative TEST

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_CTF_FADE=0"
set "QGAI_ABLATE="
set "TRAIN=C:\QGAI\engine\train.py"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "ARGS=--from 2026-04-01 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"
set "OUTBASE=C:\QGAI\backtest\results\removed_feature_top5_CUMULATIVE_TEST"
set "MODELDIR=C:\QGAI\data\models\final"
set "BACKUP=C:\QGAI\data\models\backups\TOP5_CUMULATIVE_PRE_%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "BACKUP=%BACKUP: =0%"

cd /d "%ROOT%\engine"

echo ============================================================
echo   TOP 5 REMOVED FEATURES - CUMULATIVE RETRAIN TEST
echo ------------------------------------------------------------
echo   Stage 1 3-month test: 2026-04-01 to 2026-06-29
echo.
echo   Flow:
echo     B0 = baseline current 27
echo     B1 = B0 + h4_support_dist
echo     B2 = B1 + is_dead_hour
echo     B3 = B2 + ts_line_dist_pct
echo     B4 = B3 + is_post_news
echo     B5 = B4 + move_2hr
echo.
echo   Rule after run:
echo     If next step improves Total R, candidate can stay for Stage 2.
echo     If next step reduces Total R, drop that added feature.
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

call :RUN_ONE B0_baseline ""
if errorlevel 1 goto FAIL
call :RUN_ONE B1_plus_h4_support_dist "h4_support_dist"
if errorlevel 1 goto FAIL
call :RUN_ONE B2_plus_h4support_dead_hour "h4_support_dist,is_dead_hour"
if errorlevel 1 goto FAIL
call :RUN_ONE B3_plus_line_dist "h4_support_dist,is_dead_hour,ts_line_dist_pct"
if errorlevel 1 goto FAIL
call :RUN_ONE B4_plus_post_news "h4_support_dist,is_dead_hour,ts_line_dist_pct,is_post_news"
if errorlevel 1 goto FAIL
call :RUN_ONE B5_plus_move_2hr "h4_support_dist,is_dead_hour,ts_line_dist_pct,is_post_news,move_2hr"
if errorlevel 1 goto FAIL

goto RESTORE_OK

:RUN_ONE
set "NAME=%~1"
set "ADD=%~2"
echo.
echo ------------------------------------------------------------
echo   [%NAME%]
if "%ADD%"=="" (
    echo   Candidate set: baseline current 27 features
    set "QGAI_UNPRUNE="
) else (
    echo   Candidate set: %ADD%
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
echo   Compare Total R step by step:
echo     B1 - B0, B2 - B1, B3 - B2, B4 - B3, B5 - B4
echo ============================================================
pause
exit /b 0
