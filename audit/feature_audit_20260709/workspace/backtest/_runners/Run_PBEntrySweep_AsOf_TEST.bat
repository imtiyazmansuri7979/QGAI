@echo off
title QGAI - ET1 PULLBACK-ENTRY SWEEP TEST : 2 weeks, baseline + 18 combos, as-of data (live safe)
REM ---------------------------------------------------------------------------
REM Quick pipeline test per the TEST-RUN FIRST rule. Uses the frozen as-of
REM workdir C:\QGAI_wfo_asof_rel (rel HMM). One retrain per week, then baseline +
REM 18 trend-pullback entry-param combos on that SAME model (entry isolated;
REM exit fixed live-faithful htf+regime). ML-veto OFF, runaway OFF (Sweep A).
REM Results: backtest\results\pbsweepT_<label>\ + PBSWEEPT_SUMMARY.txt/.csv
REM If clean -> Run_PBEntrySweep_AsOf_FULL.bat
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ROOT=C:\QGAI_wfo_asof_rel"
set "QGAI_HMM_VARIANT=rel"
cd /d "C:\QGAI\engine"
if not exist "C:\QGAI_wfo_asof_rel\data\merged\adx_merged.csv" (echo workdir missing - run Run_Fix1_AsOf_AB_TEST.bat step 2 first ^& pause ^& exit /b 1)
"%PY%" run_wfo.py --sweep-pb-entry --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --weeks 2 --results-dir pbsweepT
echo.
echo TEST DONE. Check: baseline + 18 combos printed R= lines for both weeks, a
echo WINNER/REJECT verdict shows, and backtest\results\PBSWEEPT_SUMMARY.csv exists.
echo Then run Run_PBEntrySweep_AsOf_FULL.bat
pause
