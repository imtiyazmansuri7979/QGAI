@echo off
setlocal
chcp 65001 >nul
title QGAI - Individual feature A/B TEST (4 features separate)

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_CTF_FADE=0"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "MODELS=C:\QGAI\data\models\final"
set "F1=h4_trending_h1_aligned"
set "F2=h4_ranging_h1_neutral"
set "F3=h4_h1_regime_score"
set "F4=trade_direction"
set "ARGS=--from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"

cd /d "%ROOT%\engine"

echo ============================================================
echo   INDIVIDUAL FEATURE A/B - 1 month smoke
echo   Baseline = 35-feat (all 4 ablated)
echo   B1 = +h4_trending_h1_aligned only
echo   B2 = +h4_ranging_h1_neutral only
echo   B3 = +h4_h1_regime_score only
echo   B4 = +trade_direction only
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [BASELINE] Retrain without all 4 features (35-feat)...
set "QGAI_ABLATE=%F1%,%F2%,%F3%,%F4%"
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN BASELINE FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" %ARGS% --out-dir "C:\QGAI\backtest\results\individual_ab_BASELINE"
if errorlevel 1 (
    echo BACKTEST BASELINE FAILED
    pause
    exit /b 1
)
echo BASELINE done.

echo.
echo [B1] Retrain +h4_trending_h1_aligned only (36-feat)...
set "QGAI_ABLATE=%F2%,%F3%,%F4%"
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN B1 FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" %ARGS% --out-dir "C:\QGAI\backtest\results\individual_ab_B1_trending_aligned"
if errorlevel 1 (
    echo BACKTEST B1 FAILED
    pause
    exit /b 1
)
echo B1 done.

echo.
echo [B2] Retrain +h4_ranging_h1_neutral only (36-feat)...
set "QGAI_ABLATE=%F1%,%F3%,%F4%"
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN B2 FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" %ARGS% --out-dir "C:\QGAI\backtest\results\individual_ab_B2_ranging_neutral"
if errorlevel 1 (
    echo BACKTEST B2 FAILED
    pause
    exit /b 1
)
echo B2 done.

echo.
echo [B3] Retrain +h4_h1_regime_score only (36-feat)...
set "QGAI_ABLATE=%F1%,%F2%,%F4%"
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN B3 FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" %ARGS% --out-dir "C:\QGAI\backtest\results\individual_ab_B3_regime_score"
if errorlevel 1 (
    echo BACKTEST B3 FAILED
    pause
    exit /b 1
)
echo B3 done.

echo.
echo [B4] Retrain +trade_direction only (36-feat)...
set "QGAI_ABLATE=%F1%,%F2%,%F3%"
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN B4 FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" %ARGS% --out-dir "C:\QGAI\backtest\results\individual_ab_B4_trade_direction"
if errorlevel 1 (
    echo BACKTEST B4 FAILED
    pause
    exit /b 1
)
echo B4 done.

echo.
echo ============================================================
echo   ALL DONE %DATE% %TIME%
echo   Results:
echo     Baseline (35): individual_ab_BASELINE
echo     B1 trending  : individual_ab_B1_trending_aligned
echo     B2 ranging   : individual_ab_B2_ranging_neutral
echo     B3 regime    : individual_ab_B3_regime_score
echo     B4 direction : individual_ab_B4_trade_direction
echo   Keep features where R beats baseline.
echo   Model on disk = B4 (last run). Retrain after decision.
echo ============================================================
pause
exit /b 0
