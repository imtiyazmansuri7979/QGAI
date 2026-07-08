@echo off
title QGAI - Build Portable Package (run on the CURRENT PC)
color 0B
echo ============================================================
echo    QGAI v2  -  BUILD PORTABLE PACKAGE
echo ------------------------------------------------------------
echo   Makes a clean, ready-to-move copy of QGAI that you copy to
echo   the new PC. Your original C:\QGAI is NOT touched / deleted.
echo   Excludes: config_mt5.py (credentials), logs, __pycache__,
echo   backtest results, old backups.
echo ============================================================
echo.
set "SRC=C:\QGAI"
set "DST=C:\QGAI_PORTABLE"

if not exist "%SRC%\engine" (
    color 0C
    echo  [ERROR] %SRC%\engine not found. Run this from the real C:\QGAI PC.
    pause & exit /b 1
)
if exist "%DST%" (
    echo  Removing old %DST% ...
    rmdir /S /Q "%DST%"
)
mkdir "%DST%"

echo  [1/6] code (engine, Start, docs, _SETUP)...
xcopy "%SRC%\engine"  "%DST%\engine\"  /E /I /Y /Q
xcopy "%SRC%\Start"   "%DST%\Start\"   /E /I /Y /Q
xcopy "%SRC%\docs"    "%DST%\docs\"    /E /I /Y /Q
xcopy "%SRC%\_SETUP"  "%DST%\_SETUP\"  /E /I /Y /Q

echo  [2/6] models + data (models, merged, live, fundamental)...
xcopy "%SRC%\data\models"      "%DST%\data\models\"      /E /I /Y /Q
xcopy "%SRC%\data\merged"      "%DST%\data\merged\"      /E /I /Y /Q
if exist "%SRC%\data\live"        xcopy "%SRC%\data\live"        "%DST%\data\live\"        /E /I /Y /Q
if exist "%SRC%\data\fundamental" xcopy "%SRC%\data\fundamental" "%DST%\data\fundamental\" /E /I /Y /Q

echo  [3/6] data files (trades + news)...
if not exist "%DST%\data" mkdir "%DST%\data"
copy "%SRC%\data\*.xlsx" "%DST%\data\" /Y >nul 2>nul
copy "%SRC%\data\*.csv"  "%DST%\data\" /Y >nul 2>nul

echo  [4/6] backtest scripts + bats (NOT the big results)...
mkdir "%DST%\backtest" 2>nul
copy "%SRC%\backtest\*.bat" "%DST%\backtest\" /Y >nul 2>nul
copy "%SRC%\backtest\*.py"  "%DST%\backtest\" /Y >nul 2>nul
copy "%SRC%\backtest\*.md"  "%DST%\backtest\" /Y >nul 2>nul

echo  [5/6] remove credentials + caches + logs from the copy...
if exist "%DST%\engine\config_mt5.py" del /Q "%DST%\engine\config_mt5.py"
if exist "%DST%\engine\logs" rmdir /S /Q "%DST%\engine\logs"
for /d /r "%DST%" %%d in (__pycache__) do @if exist "%%d" rmdir /S /Q "%%d"

echo  [6/6] done.
echo.
color 0A
echo ============================================================
echo    PACKAGE READY:  %DST%
echo ------------------------------------------------------------
echo   1) Copy the whole  %DST%  folder to the NEW PC.
echo   2) RENAME it to    C:\QGAI
echo   3) Run             C:\QGAI\_SETUP\INSTALL_QGAI.bat
echo   4) Create          C:\QGAI\engine\config_mt5.py  (credentials)
echo   5) DEMO test       C:\QGAI\Start\1_Start_Trading.bat
echo ============================================================
pause
