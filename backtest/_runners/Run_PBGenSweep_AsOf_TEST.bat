@echo off
title QGAI - ET1 v2 GENERATE-ENTRY SWEEP TEST : 2 weeks, baseline + 6 combos, as-of data (live safe)
REM ---------------------------------------------------------------------------
REM Quick pipeline test per the TEST-RUN FIRST rule. Frozen as-of workdir
REM C:\QGAI_wfo_asof_rel (rel HMM). One retrain per week, then baseline + 6
REM GENERATE-mode combos on that SAME model. GENERATE = create an early entry when
REM ML SKIPs but the dominant HTF ADX trend pulls back to the ratchet line (the real
REM "enter early, not at the top" fix — NOT just blocking). Exit fixed live-faithful.
REM Results: backtest\results\pbgensweepT_<label>\ + PBGENSWEEPT_SUMMARY.txt/.csv
REM If clean -> Run_PBGenSweep_AsOf_FULL.bat
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ROOT=C:\QGAI_wfo_asof_rel"
set "QGAI_HMM_VARIANT=rel"
cd /d "C:\QGAI\engine"
if not exist "C:\QGAI_wfo_asof_rel\data\merged\adx_merged.csv" (echo workdir missing - run Run_Fix1_AsOf_AB_TEST.bat step 2 first ^& pause ^& exit /b 1)
"%PY%" run_wfo.py --sweep-pb-gen --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --weeks 2 --results-dir pbgensweepT
echo.
echo TEST DONE. Check: baseline + 6 combos printed R= lines for both weeks, a
echo WINNER/REJECT verdict shows, and backtest\results\PBGENSWEEPT_SUMMARY.csv exists.
echo Then run Run_PBGenSweep_AsOf_FULL.bat
pause
