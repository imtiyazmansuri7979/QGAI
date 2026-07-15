@echo off
setlocal
chcp 65001 >nul
title QGAI - LeakFix P1+P2+P3 : backup + retrain + BACKTEST (1yr)

REM =====================================================================
REM  STEP 1 of 2 - BACKTEST FIRST (quick single-model sanity check).
REM  Leakage-audit fixes (2026-07-12), all HONEST (no lookahead):
REM    P1  DROP corr_imp_ratio (35->34 feat)
REM    P2  ob_strength confirm shift(-1)->shift(-2)
REM    P3  news dev_norm -> expanding past-only z-score
REM
REM  Order: RETRAIN (34 feat) -> 1-year CTF-OFF backtest (fast, ~mins).
REM  Read the Total R. If R looks sane -> run STEP 2: Run_LeakFix_P1P2P3_WFO_FULL.bat
REM
REM  NOTE: single-model backtest is mildly optimistic (train data in test).
REM  The WFO (step 2) is the honest gate. This step is just quick feedback.
REM  Default honest -- QGAI_INRANGE_LEGACY NOT set.
REM
REM  SAFETY FIX (2026-07-14, Claude): original version retrained directly into
REM  data\models\final -- the exact failure mode behind 3 same-day live-model-
REM  loss incidents (2026-07-13), fixed project-wide via QGAI_MODELS_DIR
REM  isolation. Live-checked before this fix: data\models\final was retrained
REM  TODAY 2026-07-14 07:27 (28 feat, unrelated to this leakfix work) and is
REM  NOT covered by the 2026-07-11 backup this bat used to rely on -- the old
REM  backup-then-retrain-in-place approach would have overwritten today's
REM  model with no way back. Now retrains go to data\models\test_workspace
REM  only; live model (whatever it currently is) is never touched.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_INRANGE_LEGACY="
set "QGAI_MODELS_DIR=C:\QGAI\data\models\test_workspace"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT=C:\QGAI\backtest\results\leakfix_p1p2p3_backtest_1yr"

cd /d "%ROOT%\engine"

echo ============================================================
echo   LeakFix P1+P2+P3 - retrain + 1yr backtest
echo   Expect: 34 features (corr_imp_ratio dropped)
echo   SAFE: retrain goes to data\models\test_workspace, live model untouched.
echo   %DATE% %TIME%
echo ============================================================
echo.

REM ---------- 1. RETRAIN (34 feat honest, sandboxed) ----------
echo [1/2] Retraining (34 feat, honest OB + news)...
"%PY%" train.py
if errorlevel 1 goto fail
echo.

REM ---------- 2. BACKTEST 1yr (CTF-OFF, live-parity args) ----------
echo [2/2] 1-year backtest (CTF-OFF)...
set QGAI_CTF_FADE=0
"%PY%" "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "%OUT%"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   BACKTEST DONE %DATE% %TIME%
echo   Report: %OUT%\backtest_report.txt  (read the Total R)
echo   If R looks sane -> run Run_LeakFix_P1P2P3_WFO_FULL.bat (honest gate).
echo   (No revert needed - retrain stayed in test_workspace, live model untouched.)
echo ============================================================
pause
exit /b 0

:fail
echo.
echo *** FAILED %DATE% %TIME% ***
echo   (No live-model restore needed - retrain stayed in test_workspace.)
pause
exit /b 1
