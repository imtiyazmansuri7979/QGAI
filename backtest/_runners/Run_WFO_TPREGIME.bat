@echo off
title QGAI - WFO OOS: REGIME-ADAPTIVE TP validation (Task 5)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - WFO OOS  ::  REGIME-ADAPTIVE TP  (Task 5)
echo ------------------------------------------------------------
echo   Weekly retrain on past data, trade next week UNSEEN, with
echo   TP cap switched by HMM state (Rng 2.0 / Trn 1.0 / Vol 0.8).
echo   Full year ~1.5-2 hrs. RESUME-SAFE: if it stops, run again.
echo   Results: C:\QGAI\backtest\results\wfo_tpregime\
echo.
echo   COMPARE against the global-TP baseline. For a FAIR test both
echo   must use the SAME (current) trades_file: re-run Run_WFO_FULL.bat
echo   (-^> wfo_results) on the current data too, then compare.
echo ============================================================
echo.
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 0 --risk 3 --tp-regime --results-dir wfo_tpregime
echo.
echo ============================================================
echo   WFO DONE. Now the $10k analysis:
echo     set the analyze script to read wfo_tpregime, or run
echo     Run_WFO_Analyze.bat after pointing it at wfo_tpregime.
echo   Then tell Claude "regime WFO done" to compare vs baseline.
echo ============================================================
pause
