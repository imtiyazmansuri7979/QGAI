@echo off
setlocal
chcp 65001 >nul
title QGAI - RAW H4-move A/B - WFO ~1 month (does model LEARN it in WFO?)

REM =====================================================================
REM  Raw h4_move_pct + cum3_move_pct A/B in WFO mode (~5 weeks).
REM  Single-model backtest said B (with raw) was WORSE (+6.8R vs +8.9R).
REM  But WFO RETRAINS EVERY WEEK — the model gets many chances to learn
REM  the raw feature. This short WFO checks whether that changes the verdict
REM  before committing to the full 53-week run.
REM
REM  A = WITHOUT raw (QGAI_ABLATE drops them)
REM  B = WITH raw (normal)
REM
REM  WFO retrains weekly internally (no manual retrain/backup needed).
REM  B cum R >= A -> model learns raw in WFO -> run the full 53-week WFO.
REM  B < A -> raw adds noise -> reject.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="

cd /d "%ROOT%\engine"

echo ============================================================
echo   RAW H4-move A/B - WFO ~1 month (5 weeks)
echo   %DATE% %TIME%
echo ============================================================

echo.
echo [A] WFO WITHOUT raw (ablate)...
set QGAI_ABLATE=h4_move_pct,cum3_move_pct
"%PY%" run_wfo.py --start 2026-05-25 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir rawmove_wfo_TEST_A_noraw
if errorlevel 1 goto fail

echo.
echo [B] WFO WITH raw...
set QGAI_ABLATE=
"%PY%" run_wfo.py --start 2026-05-25 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir rawmove_wfo_TEST_B_withraw
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   DONE. Compare cum R (_WFO_SUMMARY):
echo     A no-raw : rawmove_wfo_TEST_A_noraw\
echo     B with-raw: rawmove_wfo_TEST_B_withraw\
echo   B >= A -> model learns raw in WFO -> run full 53-week WFO.
echo   B <  A -> reject raw features.
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED %DATE% %TIME% ***
pause
exit /b 1
