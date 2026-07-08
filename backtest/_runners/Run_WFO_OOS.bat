@echo off
title QGAI - Walk-Forward OUT-OF-SAMPLE Validation
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - WALK-FORWARD OUT-OF-SAMPLE VALIDATION  (run_wfo.py)
echo ------------------------------------------------------------
echo   TRUE OOS: every week it retrains the model on PAST data only,
echo   then trades the NEXT week unseen. Slides forward. The model
echo   never sees future data -> the honest test of the real edge.
echo   Uses your CURRENT (pruned, 45-feature) models + buf 0.20.
echo.
echo   WARNING: SLOW - it retrains every week (full run ~1.5-2 hrs).
echo   Resume-safe: if you stop it, just run again - it continues.
echo   Per-week results saved in:  engine\wfo_results\week_*.txt
echo ============================================================
echo.
echo [QUICK TEST - first 4 weeks only, to confirm it works ~10 min]
"%PY%" run_wfo.py --start 2025-09-01 --end 2026-06-12 --buf 0.20 --tp-equity 3 --risk 3 --weeks 4
echo.
echo ============================================================
echo   Quick test done. For the FULL walk-forward run:
echo   edit this .bat and DELETE  --weeks 4  from the line above,
echo   then run again (it resumes from where it stopped).
echo ============================================================
pause
