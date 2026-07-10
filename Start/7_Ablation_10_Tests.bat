@echo off
title QGAI — 10-Test Ablation Study (Clean-34)
echo ============================================================
echo   ABLATION STUDY — 10 tests on Clean-34 base model
echo   Base = 36 features minus in_range_phase + corr_imp_ratio
echo ============================================================
echo.

set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
cd /d "C:\QGAI\engine"

"%PY%" test_ablation_10.py

echo.
echo ============================================================
echo   Done. Results saved to data\ablation_results_clean34.json
echo ============================================================
pause
