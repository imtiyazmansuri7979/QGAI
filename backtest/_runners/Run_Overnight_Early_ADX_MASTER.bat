@echo off
setlocal
chcp 65001 >nul

REM =====================================================================
REM  OVERNIGHT MASTER — Early-Entry + ADX-Strength full sweep
REM  Runs 4 backtests sequentially, resume-safe (skips if report.txt exists):
REM    1. Early-Entry TEST   (30-day smoke, ~5 min)
REM    2. Early-Entry FULL   (full-year, ~1 hr)
REM    3. ADX-Strength TEST  (30-day smoke, ~5 min)
REM    4. ADX-Strength FULL  (full-year, ~1 hr)
REM  Total ~2.5 hr. Files land under backtest\results\overnight_2026-07-07\.
REM  Baseline (SMMA OFF, gates OFF): fullbt_hmm_10k_lot001 = +350.2R
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT_ROOT=C:\QGAI\backtest\results\overnight_2026-07-07"

set "BASE_ARGS=--equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"

if not exist "%OUT_ROOT%" mkdir "%OUT_ROOT%"

cd /d "%ROOT%\engine"

echo ============================================================
echo OVERNIGHT MASTER RUN  started %DATE% %TIME%
echo ============================================================
echo Order: 1) Early TEST  2) Early FULL  3) ADX TEST  4) ADX FULL
echo Resume-safe: any run with existing backtest_report.txt is skipped.
echo ============================================================
echo.

REM ────────── 1. EARLY-ENTRY TEST ──────────
set "OUT=%OUT_ROOT%\1_early_entry_TEST_30d"
set QGAI_EARLY_DISCOUNT=1
set QGAI_ADX_STRENGTH=
set QGAI_SMMA_MTF=
echo ============================================================
echo [1/4] EARLY-ENTRY TEST  30-day smoke  %TIME%
echo   QGAI_EARLY_DISCOUNT=%QGAI_EARLY_DISCOUNT%  (must be 1)
echo ============================================================
if exist "%OUT%\backtest_report.txt" (
  echo Already done - skip.
) else (
  %PY% "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 %BASE_ARGS% --out-dir "%OUT%"
  if errorlevel 1 goto fail
)

REM ────────── 2. EARLY-ENTRY FULL ──────────
set "OUT=%OUT_ROOT%\2_early_entry_FULL_1yr"
set QGAI_EARLY_DISCOUNT=1
set QGAI_ADX_STRENGTH=
set QGAI_SMMA_MTF=
echo.
echo ============================================================
echo [2/4] EARLY-ENTRY FULL  1-year live-parity  %TIME%
echo   QGAI_EARLY_DISCOUNT=%QGAI_EARLY_DISCOUNT%  (must be 1)
echo ============================================================
if exist "%OUT%\backtest_report.txt" (
  echo Already done - skip.
) else (
  %PY% "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 %BASE_ARGS% --out-dir "%OUT%"
  if errorlevel 1 goto fail
)

REM ────────── 3. ADX-STRENGTH TEST ──────────
set "OUT=%OUT_ROOT%\3_adx_strength_TEST_30d"
set QGAI_EARLY_DISCOUNT=
set QGAI_ADX_STRENGTH=1
set QGAI_SMMA_MTF=
echo.
echo ============================================================
echo [3/4] ADX-STRENGTH TEST  30-day smoke  %TIME%
echo   QGAI_ADX_STRENGTH=%QGAI_ADX_STRENGTH%  (must be 1)
echo ============================================================
if exist "%OUT%\backtest_report.txt" (
  echo Already done - skip.
) else (
  %PY% "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 %BASE_ARGS% --out-dir "%OUT%"
  if errorlevel 1 goto fail
)

REM ────────── 4. ADX-STRENGTH FULL ──────────
set "OUT=%OUT_ROOT%\4_adx_strength_FULL_1yr"
set QGAI_EARLY_DISCOUNT=
set QGAI_ADX_STRENGTH=1
set QGAI_SMMA_MTF=
echo.
echo ============================================================
echo [4/4] ADX-STRENGTH FULL  1-year live-parity  %TIME%
echo   QGAI_ADX_STRENGTH=%QGAI_ADX_STRENGTH%  (must be 1)
echo ============================================================
if exist "%OUT%\backtest_report.txt" (
  echo Already done - skip.
) else (
  %PY% "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 %BASE_ARGS% --out-dir "%OUT%"
  if errorlevel 1 goto fail
)

echo.
echo ============================================================
echo ALL 4 RUNS DONE %DATE% %TIME%
echo Results root: %OUT_ROOT%
echo Compare vs baseline: C:\QGAI\backtest\results\fullbt_hmm_10k_lot001  (+350.2R)
echo Wake-up: report per-run Total R + WR + PF + blocked_by counts.
echo ============================================================
pause
exit /b 0

:fail
echo.
echo *** RUN FAILED %DATE% %TIME% — bat is resume-safe: fix and re-launch. ***
pause
exit /b 1
