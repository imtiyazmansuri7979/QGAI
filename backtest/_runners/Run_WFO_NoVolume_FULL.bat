@echo off
title QGAI - WFO OOS: NO-VOLUME RETRAIN FULL 53 WEEK
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - WFO OOS :: NO-VOLUME RETRAIN FULL
echo ------------------------------------------------------------
echo   Purpose:
echo     Validate the current retrained model after removing volume
echo     and tick_volume from model inputs.
echo.
echo   Model input now:
echo     34 base features + hmm_state = 35 saved model columns
echo     volume/tick_volume are NOT used as features.
echo.
echo   Settings:
echo     Period      = 2025-06-29 to 2026-06-29  (~53 weeks)
echo     buffer      = 0.15
echo     TP          = regime-adaptive (--tp-regime)
echo     tp-equity   = 0
echo     risk        = 3%%
echo.
echo   RESUME-SAFE:
echo     If this stops, run this same BAT again.
echo.
echo   Results:
echo     C:\QGAI\backtest\results\wfo_no_volume_retrain_20260710\
echo ============================================================
echo.
"%PY%" run_wfo.py --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --results-dir wfo_no_volume_retrain_20260710
echo.
echo ============================================================
echo   WFO DONE.
echo   Send Codex:
echo     no-volume wfo done, compare with 444.7R baseline
echo ============================================================
pause
