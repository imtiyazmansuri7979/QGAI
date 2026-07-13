@echo off
setlocal
chcp 65001 >nul
title QGAI - Leakage Guard Unit Tests

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

echo ============================================================
echo   LEAKAGE GUARD - UNIT TESTS  (engine\tests\test_leakage_guard.py)
echo   Fast, synthetic-data only. Does NOT touch live models. ~1 second.
echo ============================================================
echo.

"%PY%" -m unittest tests.test_leakage_guard -v
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
    echo ============================================================
    echo   ALL UNIT TESTS PASSED
    echo ============================================================
) else (
    echo ============================================================
    echo   *** UNIT TESTS FAILED *** - see output above
    echo ============================================================
)
pause
exit /b %RC%
