@echo off
title QGAI - FIX-1 WFO : REL HMM (v3 winner) on leak-free as-of data
REM Child of Run_Fix1_AsOf_AB_TEST.bat / _FULL.bat (run those - they prep the data).
REM Optional arg 1 = number of weeks (TEST mode). No arg = full 53 weeks.
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ROOT=C:\QGAI_wfo_asof_rel"
set "QGAI_HMM_VARIANT=rel"
set "EXTRA="
set "RD=wfo_asof_rel"
if not "%~1"=="" set "EXTRA=--weeks %~1"
if not "%~1"=="" set "RD=wfo_asof_rel_TEST"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   FIX-1 WFO REL on as-of data  (weeks arg: "%~1")
echo   Results: C:\QGAI\backtest\results\%RD%\
echo ============================================================
"%PY%" run_wfo.py --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime %EXTRA% --results-dir %RD%
echo.
echo DONE. Summary: C:\QGAI\backtest\results\%RD%\_WFO_SUMMARY.txt (+ .csv)
pause
