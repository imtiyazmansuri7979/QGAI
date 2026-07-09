@echo off
title QGAI - DEPLOY: retrain LIVE models with +DI/-DI HMM
REM ---------------------------------------------------------------------------
REM Run Run_Regen_ADX.bat FIRST. This retrains the LIVE models (data\models\final)
REM so the HMM uses the new +DI/-DI features, then you restart the bridge to go live.
REM Safe to run in PARALLEL with Run_HMM_DI_WFO.bat (WFO uses its own workdir).
REM
REM Backs up the current live models first -> data\models\_backup_pre_hmm_di
REM (revert = copy them back + restart, if WFO/behaviour is worse).
REM
REM *** After it finishes: READ the HMM cluster printout ***
REM   Volatile cluster should have HIGH +DI/-DI sum (real churn),
REM   Ranging should be QUIET (low sum). If labels look swapped, tell Claude.
REM Then RESTART the bridge to deploy. Profit-first: if the parallel WFO shows
REM total R worse than +483R, revert.
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"

echo ============================================================
echo   Backing up current LIVE models...
echo ============================================================
robocopy "C:\QGAI\data\models\final" "C:\QGAI\data\models\_backup_pre_hmm_di" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP >nul
echo   Backup -> C:\QGAI\data\models\_backup_pre_hmm_di

echo ============================================================
echo   Retraining LIVE models (train.py) with +DI/-DI HMM...
echo   Watch the "Cluster ... -> Volatile/Ranging" lines.
echo ============================================================
"%PY%" train.py

echo.
echo ============================================================
echo   DONE. Check the HMM cluster stats above:
echo     Volatile = HIGH +DI/-DI sum (churn) ?   Ranging = QUIET (low sum) ?
echo   If OK -> RESTART the bridge to deploy the fix.
echo   Revert = copy _backup_pre_hmm_di back into final + restart.
echo ============================================================
pause
