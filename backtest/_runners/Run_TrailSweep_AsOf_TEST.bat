@echo off
title QGAI - FIX-2 TRAIL SWEEP TEST : 2 weeks, all 6 modes, as-of data (live safe)
REM ---------------------------------------------------------------------------
REM Quick pipeline test (~15-25 min) per the TEST-RUN FIRST rule. Uses the
REM frozen as-of workdir C:\QGAI_wfo_asof_rel (rel HMM). One retrain per week,
REM then all 6 trail modes (line/off/after1r/be/htf/regime) on the same model.
REM Results: backtest\results\sweepasofT_<mode>\ + SWEEPASOFT_SUMMARY.txt/.csv
REM If clean -> Run_TrailSweep_AsOf_FULL.bat
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ROOT=C:\QGAI_wfo_asof_rel"
set "QGAI_HMM_VARIANT=rel"
cd /d "C:\QGAI\engine"
if not exist "C:\QGAI_wfo_asof_rel\data\merged\adx_merged.csv" (echo workdir missing - run Run_Fix1_AsOf_AB_TEST.bat step 2 first & pause & exit /b 1)
"%PY%" run_wfo.py --sweep-trails --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --weeks 2 --results-dir sweepasofT
echo.
echo TEST DONE. Check: all 6 modes printed R= lines for both weeks, and
echo backtest\results\SWEEPASOFT_SUMMARY.csv exists. Then run the FULL bat.
pause
