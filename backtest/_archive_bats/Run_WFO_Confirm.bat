@echo off
title QGAI - WFO CONFIRMATION RUN (fresh, full model)
REM Re-runs the full 41-week walk-forward FRESH into a NEW folder (wfo_confirm),
REM with the CURRENT committed 44-feature model (no ablation), on YOUR verified
REM Python 3.12.10. Purpose: confirm the WFO results are real/valid.
REM Compare wfo_confirm vs wfo_results (baseline +144R) — should be ~the same.
REM
REM TIP: for a FAST sanity check first, add  --weeks 2  to the line below (~15 min).
REM Remove it for the full ~10-13 hr run. Resume-safe.
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
REM make sure no ablation is active for the confirm run:
set "QGAI_ABLATE="
cd /d "C:\QGAI\engine"
echo ============================================================
echo   WFO CONFIRMATION (fresh) -^> backtest\results\wfo_confirm\
echo   Full 44-feature model, verified Python. Resume-safe.
echo   (add --weeks 2 in the .bat for a quick 15-min sanity check)
echo ============================================================
echo.
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --fixed-lot 0.01 --results-dir wfo_confirm
echo.
echo Done. Tell Claude "confirm done" to compare wfo_confirm vs wfo_results.
pause
