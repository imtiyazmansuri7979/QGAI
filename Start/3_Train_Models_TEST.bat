@echo off
title QGAI - TEST (RAW tick_volume feature smoke test)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - TEST RUN (does NOT train / does NOT touch live .pkl)
echo   Smoke-checks the new RAW tick_volume feature end-to-end:
echo     - tick_volume in FEATURE_COLS, normalized volume pruned
echo     - feature matrix builds with no crash / no KeyError
echo     - tick_volume column = real RAW varying counts
echo   Run THIS first. Only after it PASSES, run 3_Train_Models.bat
echo ============================================================
echo.
"%PY%" test_tickvol_feature.py
echo.
echo ============================================================
echo   TEST finished. Press any key to close.
echo ============================================================
pause >nul
