@echo off
title QGAI - STEP 1: Rebuild adx_merged.csv with +DI/-DI
REM ---------------------------------------------------------------------------
REM RUN THIS FIRST (before Deploy or WFO). Rebuilds data\merged\adx_merged.csv
REM to include {TF}_PlusDI / {TF}_MinusDI (needed by the new +DI/-DI HMM).
REM Additive: old ADX/DI_diff preserved, old file backed up (.bak_prediregen),
REM prints a DI_diff PARITY report. ~seconds. Does NOT touch models or live.
REM After this: run Run_HMM_DI_Deploy.bat AND Run_HMM_DI_WFO.bat (parallel OK).
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
"%PY%" regen_adx_di.py
echo.
echo ^>^> Check DI_diff PARITY above. Small max^|delta^| = OK to proceed.
echo    Large delta = STOP, tell Claude before deploying/retraining.
pause
