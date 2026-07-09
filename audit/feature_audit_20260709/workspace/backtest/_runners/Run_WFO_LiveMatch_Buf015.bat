@echo off
title QGAI - WFO OOS: LIVE-MATCH (buf 0.15, same period as live_buffer_015)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - WFO OOS  ::  LIVE-MATCH validation
echo ------------------------------------------------------------
echo   Weekly retrain on past data, trade next week UNSEEN.
echo   Matches CURRENT live config exactly:
echo     buffer      = 0.15  (was 0.20 in old wfo_results/wfo_tpregime runs)
echo     TP          = regime-adaptive (--tp-regime, config default ON)
echo     tp-equity   = 0  (price-cap TP, matches live)
echo     risk        = 3%%
echo     HTF SL/flip/forming, skip-counter-trend-fade: read from config.py
echo       (same file live trades with) - no CLI override needed.
echo   SAME PERIOD as live_buffer_015 (2025-06-29 -^> 2026-06-29) so the
echo   PF/DD/R here is a fair apples-to-apples OOS check against that
echo   full-year in-sample run.
echo   Full year ~1.5-2.5 hrs. RESUME-SAFE: if it stops, run again.
echo   Results: C:\QGAI\backtest\results\wfo_live_match_015\
echo ============================================================
echo.
"%PY%" run_wfo.py --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --results-dir wfo_live_match_015
echo.
echo ============================================================
echo   WFO DONE. Tell Claude "wfo live-match done" to analyze
echo   (PF, max DD, OOS R) against live_buffer_015 in-sample numbers.
echo ============================================================
pause
