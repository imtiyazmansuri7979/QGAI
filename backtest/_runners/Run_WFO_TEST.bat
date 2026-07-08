@echo off
title QGAI - WFO **TEST** (first few weeks only — smoke test before full)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - WFO TEST  (first 3 weeks only, weekly retrain)
echo   Confirms the WFO pipeline runs end-to-end on the current
echo   (relabeled) model BEFORE the ~1.5-2 hr full run.
echo   Runs BOTH: global TP  +  regime-adaptive TP.
echo ============================================================
echo.
echo ----- [1/2] global TP (baseline) -------------------------
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 0 --risk 3 --weeks 3 --results-dir wfo_test_global
echo.
echo ----- [2/2] regime-adaptive TP ---------------------------
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 0 --risk 3 --weeks 3 --tp-regime --results-dir wfo_test_regime
echo.
echo ============================================================
echo   TEST done, no errors? -^> run the FULL:
echo     Run_WFO_FULL.bat   and   Run_WFO_TPREGIME.bat
echo ============================================================
pause
