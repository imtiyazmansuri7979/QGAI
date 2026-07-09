@echo off
title QGAI - AUDIT FIX 1 : leak-free (as-of) ADX regen + honest re-baseline
REM ---------------------------------------------------------------------------
REM Removes the confirmed intra-bar HTF lookahead from training/backtest data.
REM RUN ONLY AFTER the A/B HMM WFO windows are FINISHED (they use frozen data,
REM but keep runs comparable - one change at a time).
REM
REM Steps: 1) preview as-of file + leak drift report
REM        2) ask before --apply (backs up old file automatically)
REM After apply: retrain + RERUN WFO. That new total R = the HONEST baseline.
REM Do NOT compare the new WFO against +483.1R (leak-inflated number).
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"

echo [1/2] Preview + leak drift report (writes adx_merged_asof.csv, live file untouched)
"%PY%" regen_adx_asof.py
echo.
echo Review the LEAK DRIFT numbers above.
pause

echo [2/2] APPLY (backup + replace adx_merged.csv with the as-of version)
"%PY%" regen_adx_asof.py --apply
echo.
echo DONE. NEXT: (a) retrain via Run_HMM_v3_Deploy.bat pattern, (b) rerun the WFO
echo (winner variant) to get the HONEST baseline, (c) update mt5_data_updater to
echo the as-of convention together with the retrain (ask Claude - one atomic switch).
pause
