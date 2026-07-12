@echo off
setlocal
chcp 65001 >nul
title QGAI - ADX Redundancy A/B TEST

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_CTF_FADE=0"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "ARGS=--from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"

cd /d "%ROOT%\engine"

echo ============================================================
echo   ADX REDUNDANCY A/B - 1 month
echo   Baseline = current (with B1/B2/B4 pruned, B3 kept)
echo   D1 = drop h4_ranging_h1_extended (B3 score=-1 covers it)
echo   D2 = drop M30_ADX (middle TF redundant)
echo   D3 = drop H1_ADX (h1_adx_slope + H1_DI covers it)
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [BASELINE] Retrain current config (36-feat, B3 only)...
set "QGAI_ABLATE="
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN BASELINE FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" %ARGS% --out-dir "C:\QGAI\backtest\results\adx_redundancy_BASELINE"
if errorlevel 1 (
    echo BACKTEST BASELINE FAILED
    pause
    exit /b 1
)
echo BASELINE done.

echo.
echo [D1] Drop h4_ranging_h1_extended...
set "QGAI_ABLATE=h4_ranging_h1_extended"
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN D1 FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" %ARGS% --out-dir "C:\QGAI\backtest\results\adx_redundancy_D1_no_extended"
if errorlevel 1 (
    echo BACKTEST D1 FAILED
    pause
    exit /b 1
)
echo D1 done.

echo.
echo [D2] Drop M30_ADX...
set "QGAI_ABLATE=M30_ADX"
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN D2 FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" %ARGS% --out-dir "C:\QGAI\backtest\results\adx_redundancy_D2_no_M30ADX"
if errorlevel 1 (
    echo BACKTEST D2 FAILED
    pause
    exit /b 1
)
echo D2 done.

echo.
echo [D3] Drop H1_ADX...
set "QGAI_ABLATE=H1_ADX"
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN D3 FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" %ARGS% --out-dir "C:\QGAI\backtest\results\adx_redundancy_D3_no_H1ADX"
if errorlevel 1 (
    echo BACKTEST D3 FAILED
    pause
    exit /b 1
)
echo D3 done.

echo.
echo ============================================================
echo   ALL DONE %DATE% %TIME%
echo   Results:
echo     Baseline    : adx_redundancy_BASELINE
echo     D1 no ext   : adx_redundancy_D1_no_extended
echo     D2 no M30ADX: adx_redundancy_D2_no_M30ADX
echo     D3 no H1ADX : adx_redundancy_D3_no_H1ADX
echo   Drop = R same or better than baseline.
echo ============================================================
pause
exit /b 0
