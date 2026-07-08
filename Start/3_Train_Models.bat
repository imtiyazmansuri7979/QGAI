@echo off
title QGAI - Train Models
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   QGAI - RETRAIN MODELS
echo   Step 1: merge historical + live data (merge_data.py)
echo   Step 2: train models (train.py)
echo ============================================================
echo.
echo [1/2] Merging data...
"%PY%" merge_data.py
if errorlevel 1 (
    echo.
    echo  ^!^! Data merge FAILED - stopping before training.
    pause >nul
    exit /b 1
)
echo.
echo [2/2] Training models...
"%PY%" train.py
echo.
echo ============================================================
echo   Training finished. Press any key to close.
echo ============================================================
pause >nul
