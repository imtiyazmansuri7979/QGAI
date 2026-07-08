@echo off
title QGAI v2 - New PC Installer
setlocal enabledelayedexpansion
color 0B
echo ============================================================
echo    QUANT GOLD AI v2  -  NEW PC INSTALLER
echo ============================================================
echo   This installs the Python packages QGAI needs.
echo   (Python 3.11/3.12 and MetaTrader5 terminal must already
echo    be installed separately - see SETUP_NEW_PC_GU.md.)
echo ============================================================
echo.

REM ---- 1. Find Python -----------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PY (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
)
if not defined PY (
    color 0C
    echo  [ERROR] Python not found.
    echo  Install Python 3.12 from https://www.python.org/downloads/
    echo  IMPORTANT: tick "Add Python to PATH" during install, then run this again.
    echo.
    pause
    exit /b 1
)
echo  [OK] Python found:  %PY%
%PY% --version
echo.

REM ---- 2. Upgrade pip -----------------------------------------
echo  [1/3] Upgrading pip...
%PY% -m pip install --upgrade pip

REM ---- 3. Install packages ------------------------------------
echo.
echo  [2/3] Installing QGAI packages (this can take a few minutes)...
%PY% -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    color 0C
    echo  [ERROR] Package install failed. Check your internet connection and re-run.
    pause
    exit /b 1
)

REM ---- 4. Verify ----------------------------------------------
echo.
echo  [3/3] Verifying imports...
%PY% -c "import MetaTrader5, xgboost, lightgbm, catboost, pandas, numpy, scipy, sklearn, joblib, openpyxl; print('  [OK] All core packages import fine')"
if errorlevel 1 (
    color 0C
    echo  [WARN] Some package failed to import - re-run or check the error above.
    pause
    exit /b 1
)

echo.
color 0A
echo ============================================================
echo    INSTALL COMPLETE  ^|  next steps:
echo ============================================================
echo   1) Install the MetaTrader5 terminal + log in (broker).
echo   2) Create  C:\QGAI\engine\config_mt5.py  with your login/
echo      password/server/symbol  (copy engine\config_mt5_template.py).
echo   3) Start trading:  C:\QGAI\Start\1_Start_Trading.bat
echo.
echo   (Test on a DEMO account first - see docs\USER_GUIDE_GU.md)
echo ============================================================
pause
