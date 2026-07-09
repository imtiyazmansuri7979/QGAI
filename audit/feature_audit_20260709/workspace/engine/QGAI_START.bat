@echo off
title QUANT GOLD AI v2
color 0A
cls

:: Self-relative paths — works wherever QGAI folder is placed
set "ENGINE_DIR=%~dp0"
set "QGAI_ROOT=%~dp0.."

echo ============================================================
echo   QUANT GOLD AI v2
echo   %date%  %time%
echo   Root: %QGAI_ROOT%
echo ============================================================
echo.

if not exist "%ENGINE_DIR%config_mt5.py" (
    echo ERROR: config_mt5.py not found!
    echo Copy config_mt5_template.py to config_mt5.py and fill in your MT5 credentials
    echo Expected location: %ENGINE_DIR%config_mt5.py
    pause
    exit /b 1
)

if not exist "%QGAI_ROOT%\data\models\final\xgb_model.pkl" (
    echo ERROR: Models not found!
    echo Run QGAI_RETRAIN.bat first to train the models
    echo Expected location: %QGAI_ROOT%\data\models\final\
    pause
    exit /b 1
)

echo Opening dashboard...
:: FIX #13: dashboard opened via file:// could not fetch /logs/dashboard.json
:: — it must be served over http. Start the server, then open localhost.
start "QGAI Dashboard Server" cmd /c "cd /d "%ENGINE_DIR%" && python serve.py"
timeout /t 2 /nobreak >nul
start "" "http://localhost:8000/dashboard.html"
timeout /t 2 /nobreak >nul

echo.
echo Starting QGAI Bridge...
echo.
cd /d "%ENGINE_DIR%"
python bridge_main.py

pause
