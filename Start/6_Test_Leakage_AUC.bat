@echo off
title QGAI — Leakage AUC Impact Test
color 0E
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cls

echo ============================================================
echo   LEAKAGE AUC TEST
echo   Compares AUC with/without leaky features:
echo     - in_range_phase  (rank #1, H4 lookahead)
echo     - corr_imp_ratio  (rank #28, swing lookahead)
echo   No models saved — test only, safe to run.
echo ============================================================
echo.

cd /d "C:\QGAI\engine"
"%PY%" test_leakage_auc.py
echo.
pause
