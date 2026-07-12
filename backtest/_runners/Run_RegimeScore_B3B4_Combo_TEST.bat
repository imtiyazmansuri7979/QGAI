@echo off
setlocal
chcp 65001 >nul
title QGAI - B3+B4 Combo TEST (regime_score + trade_direction)

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_CTF_FADE=0"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"

cd /d "%ROOT%\engine"

echo ============================================================
echo   B3+B4 COMBO TEST - 1 month
echo   Baseline = 35-feat (all 4 ablated)
echo   Combo = 37-feat (h4_h1_regime_score + trade_direction)
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [BASELINE] Retrain 35-feat (all 4 ablated)...
set "QGAI_ABLATE=h4_trending_h1_aligned,h4_ranging_h1_neutral,h4_h1_regime_score,trade_direction"
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN BASELINE FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "C:\QGAI\backtest\results\combo_b3b4_BASELINE"
if errorlevel 1 (
    echo BACKTEST BASELINE FAILED
    pause
    exit /b 1
)

echo.
echo [COMBO] Retrain 37-feat (h4_h1_regime_score + trade_direction)...
set "QGAI_ABLATE=h4_trending_h1_aligned,h4_ranging_h1_neutral"
"%PY%" train.py
if errorlevel 1 (
    echo TRAIN COMBO FAILED
    pause
    exit /b 1
)
"%PY%" "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "C:\QGAI\backtest\results\combo_b3b4_WITH"
if errorlevel 1 (
    echo BACKTEST COMBO FAILED
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   DONE %DATE% %TIME%
echo   Baseline (35): combo_b3b4_BASELINE
echo   Combo (37)   : combo_b3b4_WITH
echo   Model on disk = Combo (37-feat)
echo ============================================================
pause
exit /b 0
