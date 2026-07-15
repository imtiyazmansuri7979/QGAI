@echo off
setlocal
chcp 65001 >nul
title QGAI - LeakFix P1+P2+P3 : FULL WFO (53 weeks) - honest gate

REM =====================================================================
REM  WFO honest gate. Can run standalone -- run_wfo.py retrains its own
REM  fresh model each of the 53 weekly folds from the CURRENT features.py
REM  code (P1/P2/P3 fixes are permanent code changes, always active), into
REM  the isolated test_workspace folder below. Running the single-model
REM  Run_LeakFix_P1P2P3_Retrain_Backtest.bat first is optional quick feedback,
REM  not a hard prerequisite.
REM
REM  GATE: honest baseline ~+80R (W13 corr_imp-out = +80.5R).
REM  PASS if Total R >= ~+78R (within noise) -> adopt P1+P2+P3.
REM  Big drop -> a fix cut real signal -> investigate before adopting.
REM
REM  ~2-3 hours. Resume-safe. Default honest -- QGAI_INRANGE_LEGACY NOT set.
REM
REM  SAFETY FIX (2026-07-14, Claude): this bat is from 2026-07-12, BEFORE the
REM  2026-07-13 root-cause fix for 3 same-day live-model-loss incidents
REM  (QGAI_MODELS_DIR test_workspace isolation). The original version retrained
REM  directly into data\models\final on EVERY one of the 53 weekly WFO folds --
REM  the exact failure mode that caused those incidents. Added QGAI_MODELS_DIR
REM  below so every fold retrain goes to a separate sandbox folder instead;
REM  your live model (whatever it currently is) is now NEVER touched, and the
REM  live bridge can keep running unaffected during this ~2-3 hour run.
REM  (Found live-checking before this run: data\models\final was retrained
REM  TODAY 2026-07-14 07:27, 28 features -- unrelated to this leakfix work and
REM  NOT covered by the 2026-07-11 backup below. This fix protects it too.)
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"
set "BACKUP=C:\QGAI\data\models\_backup_pre_leakfix_p1p2p3_20260712"

cd /d "%ROOT%\engine"

echo ============================================================
echo   LeakFix P1+P2+P3 - FULL WFO (53 weeks)
echo   Gate: Total R >= ~+78R (honest baseline ~+80R)
echo   SAFE: retrains go to data\models\test_workspace, live model untouched.
echo   %DATE% %TIME%
echo ============================================================
echo.

echo Running full WFO (2025-06-23 to 2026-06-29)...
"%PY%" run_wfo.py --start 2025-06-23 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --fixed-lot 0.01 --results-dir wfo_leakfix_p1p2p3_20260712
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   DONE %DATE% %TIME%
echo   Results: backtest\results\wfo_leakfix_p1p2p3_20260712\
echo   GATE: Total R >= ~+78R => adopt P1+P2+P3 (honest baseline).
echo   If big drop: investigate which fix cut signal.
echo   (No revert needed - retrains stayed in test_workspace, live model untouched.)
echo ============================================================
pause
exit /b 0

:fail
echo.
echo *** FAILED %DATE% %TIME% ***
echo   (No live-model restore needed - retrains stayed in test_workspace.)
pause
exit /b 1
