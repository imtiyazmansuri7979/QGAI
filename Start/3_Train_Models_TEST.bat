@echo off
title QGAI - TEST (volume feature removed smoke test)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - TEST RUN (does NOT train / does NOT touch live .pkl)
echo   Smoke-checks volume removal from model inputs:
echo     - tick_volume NOT in FEATURE_COLS
echo     - normalized volume NOT in FEATURE_COLS
echo     - feature matrix builds with no crash / no KeyError
echo     - model matrix has no volume columns
echo   Run THIS first. Only after it PASSES, run 3_Train_Models.bat
echo ============================================================
echo.
"%PY%" test_tickvol_feature.py
echo.
echo ============================================================
echo   TEST finished. Press any key to close.
echo ============================================================
pause >nul
