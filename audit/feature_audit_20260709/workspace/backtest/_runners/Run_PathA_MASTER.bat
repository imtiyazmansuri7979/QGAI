@echo off
setlocal
chcp 65001 >nul

REM =====================================================================
REM  PATH A MASTER — 4 FULL-YEAR A/B tests (TESTs skipped, smoke already
REM  passed inline for CTF/Range/Early-v2/Stacked configs 2026-07-07).
REM  Baseline: fullbt_hmm_10k_lot001 = +350.2R
REM
REM  Order (~4 hr total, resume-safe):
REM   1. CTF-OFF            QGAI_CTF_FADE=0
REM   2. Range-soften       QGAI_RANGE_MIN_PROB=0.55
REM   3. Early-entry v2     QGAI_EARLY_DISCOUNT=1 + Fable loose guards
REM   4. STACKED (all 3)
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT_ROOT=C:\QGAI\backtest\results\path_A_2026-07-07"

set "BASE_ARGS=--equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"

if not exist "%OUT_ROOT%" mkdir "%OUT_ROOT%"
cd /d "%ROOT%\engine"

echo ============================================================
echo PATH A MASTER  started %DATE% %TIME%
echo Goal: +70R (20%%) to +175R (50%%) lift over baseline +350.2R
echo ============================================================
echo.

REM ─────────── 1. CTF-OFF FULL ───────────
set QGAI_CTF_FADE=0
set QGAI_RANGE_MIN_PROB=
set QGAI_EARLY_DISCOUNT=
set QGAI_ED_HTF_RULE=
set QGAI_ED_ADX_SLOPE_GUARD=
set QGAI_ED_STATE_PROB_MIN=
set QGAI_ED_DELTA=

set "OUT=%OUT_ROOT%\1_ctf_off_FULL_1yr"
echo === [1/4] CTF-OFF FULL 1-year  QGAI_CTF_FADE=%QGAI_CTF_FADE% ===
if exist "%OUT%\backtest_report.txt" ( echo Done - skip. ) else (
  %PY% "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 %BASE_ARGS% --out-dir "%OUT%"
  if errorlevel 1 goto fail
)

REM ─────────── 2. RANGE-SOFTEN 0.55 FULL ───────────
set QGAI_CTF_FADE=
set QGAI_RANGE_MIN_PROB=0.55
set QGAI_EARLY_DISCOUNT=

set "OUT=%OUT_ROOT%\2_range_soft_FULL_1yr"
echo === [2/4] RANGE-SOFTEN 0.55 FULL 1-year  QGAI_RANGE_MIN_PROB=%QGAI_RANGE_MIN_PROB% ===
if exist "%OUT%\backtest_report.txt" ( echo Done - skip. ) else (
  %PY% "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 %BASE_ARGS% --out-dir "%OUT%"
  if errorlevel 1 goto fail
)

REM ─────────── 3. EARLY-ENTRY v2 FULL ───────────
set QGAI_CTF_FADE=
set QGAI_RANGE_MIN_PROB=
set QGAI_EARLY_DISCOUNT=1
set QGAI_ED_HTF_RULE=adx_switch
set QGAI_ED_ADX_SLOPE_GUARD=0
set QGAI_ED_STATE_PROB_MIN=0.55
set QGAI_ED_DELTA=0.08

set "OUT=%OUT_ROOT%\3_early_v2_FULL_1yr"
echo === [3/4] EARLY-V2 FULL 1-year  rule=%QGAI_ED_HTF_RULE% slope=%QGAI_ED_ADX_SLOPE_GUARD% sp=%QGAI_ED_STATE_PROB_MIN% d=%QGAI_ED_DELTA% ===
if exist "%OUT%\backtest_report.txt" ( echo Done - skip. ) else (
  %PY% "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 %BASE_ARGS% --out-dir "%OUT%"
  if errorlevel 1 goto fail
)

REM ─────────── 4. STACKED FULL (all 3 together) ───────────
set QGAI_CTF_FADE=0
set QGAI_RANGE_MIN_PROB=0.55
set QGAI_EARLY_DISCOUNT=1
set QGAI_ED_HTF_RULE=adx_switch
set QGAI_ED_ADX_SLOPE_GUARD=0
set QGAI_ED_STATE_PROB_MIN=0.55
set QGAI_ED_DELTA=0.08

set "OUT=%OUT_ROOT%\4_STACKED_FULL_1yr"
echo === [4/4] STACKED FULL 1-year  (CTF-OFF + Range-0.55 + Early-v2) ===
if exist "%OUT%\backtest_report.txt" ( echo Done - skip. ) else (
  %PY% "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 %BASE_ARGS% --out-dir "%OUT%"
  if errorlevel 1 goto fail
)

echo.
echo ============================================================
echo ALL 4 PATH A FULL RUNS DONE %DATE% %TIME%
echo Root: %OUT_ROOT%
echo Baseline reference: fullbt_hmm_10k_lot001 = +350.2R
echo Compare per-run Total R + WR + PF + DD + blocked_by counts.
echo ============================================================
pause
exit /b 0

:fail
echo *** RUN FAILED %DATE% %TIME% — resume-safe: fix and re-launch. ***
pause
exit /b 1
