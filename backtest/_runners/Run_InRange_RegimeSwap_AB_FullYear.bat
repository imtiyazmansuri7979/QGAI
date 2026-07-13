@echo off
setlocal
chcp 65001 >nul
title QGAI - in_range_phase REGIME-SWAP A/B - FULL YEAR

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_CTF_FADE=0"
set "QGAI_ABLATE="
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"

cd /d "%ROOT%\engine"

echo ============================================================
echo   in_range_phase REGIME-SWAP A/B - FULL YEAR
echo   A = OFF (global 0.5%%)
echo   B = ON (Trending 0.5%% / Volatile 0.6%%)
echo   Model: 33-feat (current code, fresh retrain first)
echo   %DATE% %TIME%
echo ============================================================

REM Retrain skipped - model already 33-feat (retrained 2026-07-12)

echo.
echo [A] OFF - global 0.5%% cutoff (full year)...
set QGAI_REGIME_INRANGE=0
"%PY%" "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "C:\QGAI\backtest\results\inrange_regimeswap_FULL_A_off"
if errorlevel 1 (
    echo BACKTEST A FAILED
    pause
    exit /b 1
)

echo.
echo [B] ON - regime-aware cutoff (full year)...
set QGAI_REGIME_INRANGE=1
"%PY%" "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "C:\QGAI\backtest\results\inrange_regimeswap_FULL_B_on"
if errorlevel 1 (
    echo BACKTEST B FAILED
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   DONE %DATE% %TIME%
echo   A off: inrange_regimeswap_FULL_A_off\backtest_report.txt
echo   B on : inrange_regimeswap_FULL_B_on\backtest_report.txt
echo   B >= A = confirmed. B less A = revert (QGAI_REGIME_INRANGE=0)
echo ============================================================
pause
exit /b 0
