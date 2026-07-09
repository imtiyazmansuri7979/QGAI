@echo off
title QGAI - ET1 v2 GENERATE-ENTRY SWEEP FULL : full year, baseline + 6 combos, as-of data (live safe)
REM ---------------------------------------------------------------------------
REM FULL run — ONLY after Run_PBGenSweep_AsOf_TEST.bat is clean. Leak-free as-of
REM workdir C:\QGAI_wfo_asof_rel (rel HMM). One retrain per week, then baseline +
REM 6 GENERATE-mode combos on that SAME model. GENERATE = create an early entry
REM when ML SKIPs but the dominant HTF ADX trend pulls back to the ratchet line.
REM Exit fixed live-faithful (htf+regime).
REM ACCEPTANCE: adopt the combo with the highest total R that BEATS baseline.
REM   If NO combo beats baseline -> REJECT (house rule: PROFIT = total R).
REM Results: backtest\results\pbgensweep_<label>\ + PBGENSWEEP_SUMMARY.txt/.csv
REM Cached weeks are skipped, so a killed run resumes where it stopped.
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ROOT=C:\QGAI_wfo_asof_rel"
set "QGAI_HMM_VARIANT=rel"
cd /d "C:\QGAI\engine"
if not exist "C:\QGAI_wfo_asof_rel\data\merged\adx_merged.csv" (echo workdir missing - run Run_Fix1_AsOf_AB_TEST.bat step 2 first ^& pause ^& exit /b 1)
"%PY%" run_wfo.py --sweep-pb-gen --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --results-dir pbgensweep
echo.
echo FULL DONE. Open backtest\results\PBGENSWEEP_SUMMARY.csv — combos ranked by total R
echo (vs_baseline column). Adopt the WINNER only if it beats baseline; else REJECT.
pause
