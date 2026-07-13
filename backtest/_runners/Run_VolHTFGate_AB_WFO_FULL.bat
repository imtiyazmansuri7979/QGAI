@echo off
setlocal
chcp 65001 >nul
title QGAI - Volatile counter-HTF gate A/B - WFO FULL (53 weeks)

REM =====================================================================
REM  FULL 53-week confirm of Run_VolHTFGate_AB_WFO_TEST.bat - only run this
REM  AFTER the 3-month TEST bat showed B >= A. Same A/B design, full honest
REM  WFO window (matches wfo_adxdeath_novol_baseline_20260710 / the
REM  +80.5R honest baseline this whole finding was measured against).
REM
REM  A = baseline (QGAI_VOL_HTF_GATE=0, current live behavior)
REM  B = candidate (QGAI_VOL_HTF_GATE=1, skips Volatile+42-48%+counter-HTF)
REM
REM  DECISION RULE: adopt (flip default to 1 in inference.py) ONLY if
REM  B total R >= A total R, DD not worse, and losses aren't concentrated
REM  in a small number of folds (check per-week _WFO_SUMMARY breakdown,
REM  not just the cumulative total).
REM
REM  SAFE BY DESIGN (2026-07-13, root-cause fix after 3 same-day model-loss
REM  incidents): every weekly retrain goes to data\models\test_workspace
REM  (separate from data\models\final) via QGAI_MODELS_DIR. Your live model
REM  is NEVER touched - the live bridge can even run at the same time.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"

cd /d "%ROOT%\engine"

echo ============================================================
echo   VOLATILE COUNTER-HTF GATE A/B - WFO FULL (53 weeks)
echo   %DATE% %TIME%
echo   WARNING: this is a long run (53 weekly retrains x 2 configs).
echo ============================================================

echo.
echo [A] WFO baseline (gate OFF)...
set "QGAI_VOL_HTF_GATE=0"
"%PY%" run_wfo.py --start 2025-06-23 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir volhtfgate_wfo_FULL_A_off
if errorlevel 1 goto fail

echo.
echo [B] WFO candidate (gate ON)...
set "QGAI_VOL_HTF_GATE=1"
"%PY%" run_wfo.py --start 2025-06-23 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir volhtfgate_wfo_FULL_B_on
if errorlevel 1 goto fail
set "QGAI_VOL_HTF_GATE="

echo.
echo ============================================================
echo   DONE. Compare cum R (_WFO_SUMMARY.csv):
echo     A (gate OFF): backtest\results\volhtfgate_wfo_FULL_A_off\
echo     B (gate ON) : backtest\results\volhtfgate_wfo_FULL_B_on\
echo   Adopt live ONLY if B >= A, DD not worse, and gains aren't from 1-2 folds.
echo ============================================================
pause
exit /b 0

:fail
set "QGAI_VOL_HTF_GATE="
echo *** FAILED %DATE% %TIME% ***
pause
exit /b 1
