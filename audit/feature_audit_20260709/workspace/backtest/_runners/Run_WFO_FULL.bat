@echo off
title QGAI - FULL Walk-Forward OOS Validation
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - FULL WALK-FORWARD OUT-OF-SAMPLE  (all weeks)
echo ------------------------------------------------------------
echo   True OOS: weekly retrain on past data, trade next week unseen.
echo   Full year ~1.5-2 hrs. RESUME-SAFE: if it stops, run again.
echo   Results saved in:  C:\QGAI\backtest\results\wfo_results\
echo ============================================================
echo.
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 0 --risk 3
echo.
REM 2026-06-27: --tp-equity 0 (was 3). With 3 the equity-TP path bypassed the price TP cap
REM entirely (and under fixed-lot it never fired) so TP was inert + didn't match live. 0 = use
REM the config price TP cap (1.0%), matching live and letting regime-TP actually act.
echo ============================================================
echo   WFO DONE. Now run the $10k weekly/monthly analysis:
echo     double-click  Run_WFO_Analyze.bat
echo ============================================================
pause
