@echo off
setlocal
chcp 65001 >nul

REM =====================================================================
REM  SMMA MTF soft gate — LIVE-PARITY FULL-YEAR BT
REM  Uses backtest_replay.py (live code path) with QGAI_SMMA_MTF=1.
REM  Compares against existing live-parity baseline (fullbt_hmm_10k_lot001).
REM  Expected: SMMA ON >> baseline +350.2R  (research says +51R lift).
REM  If confirmed -> flip cfg.filters.smma_mtf_soft=True + DEMO → live.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT=C:\QGAI\backtest\results\smma_parity_fullbt_smmaON"

set QGAI_SMMA_MTF=1

echo ============================================================
echo FULL-year live-parity BT with SMMA gate ON
echo 2025-06-29 -^> 2026-06-29  ~1 hour
echo ------------------------------------------------------------
echo QGAI_SMMA_MTF = %QGAI_SMMA_MTF%   (must be 1)
echo SCRIPT        = %SCRIPT%
echo OUT           = %OUT%
echo ============================================================
if not "%QGAI_SMMA_MTF%"=="1" (
  echo *** ABORT: QGAI_SMMA_MTF is not 1  gate would be OFF. ***
  pause
  exit /b 1
)
cd /d "%ROOT%\engine"
%PY% "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "%OUT%"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo DONE. Compare vs existing baseline:
echo   Baseline (SMMA OFF): C:\QGAI\backtest\results\fullbt_hmm_10k_lot001
echo   SMMA ON            : %OUT%
echo Look at: Total R, WR, PF, DD, blocked_by=smma_mtf count.
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED — check log. ***
pause
exit /b 1
