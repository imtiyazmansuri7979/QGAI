@echo off
setlocal
chcp 65001 >nul
title QGAI - Overnight: max_open risk/reward + per-regime TP sweep

REM =====================================================================
REM  ONE overnight master, RESUME-SAFE (skips any run whose report exists).
REM  Whatever finishes by morning is progress; re-run to continue.
REM  Each full-year run ~60-70 min on this PC.
REM
REM  PHASE 1 — max_open risk/reward (dynamic 3%% compounding + dd-brake, REAL DD):
REM    A. max_open=1 @ 3%%        (3%% total, baseline)
REM    B. max_open=2 @ 1.5%% each (3%% total, risk-neutral)
REM    C. max_open=2 @ 2%% each   (4%% total, Imtiyaz's pick)
REM
REM  PHASE 2 — per-regime TP-cap COARSE coordinate descent (Fable-5 C),
REM    fixed-lot 0.01 (fast, R-comparison), one regime varied, others at current.
REM    Current defaults = Rng 2.0 / Trn 1.0 / Vol 0.8. Env QGAI_TP_REGIME_VALS="R,T,V".
REM    Ranging : 1.6 , 2.4 , 2.8   (Trn 1.0 / Vol 0.8 held)
REM    Trending: 0.8 , 1.2 , 1.4   (Rng 2.0 / Vol 0.8 held)
REM    Volatile: 0.6 , 1.0 , 1.2   (Rng 2.0 / Trn 1.0 held)
REM   (baseline Rng2/Trn1/Vol0.8 already = PHASE-1 run A, no need to repeat)
REM
REM  ⚠️ Backtest-side only, live untouched, validated raw-36 model.
REM  Total ~12-13 hr full. Leave running; resume-safe.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT=C:\QGAI\backtest\results\overnight_maxopen_tp_2026-07-08"
set "YEAR=--from 2025-06-29 --to 2026-06-29"

if not exist "%OUT%" mkdir "%OUT%"
cd /d "%ROOT%\engine"
echo ============================================================
echo OVERNIGHT MASTER  %DATE% %TIME%
echo ============================================================

REM ===================== PHASE 1 — max_open =====================
set "DYN=%YEAR% --equity 10000 --fixed-lot 0 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --dd-brake"
set QGAI_TP_REGIME_VALS=

echo [P1-A] max_open=1 @ 3%%...
if not exist "%OUT%\P1_A_open1_r3\backtest_report.txt" ( "%PY%" "%SCRIPT%" %DYN% --max-open 1 --risk 3 --out-dir "%OUT%\P1_A_open1_r3" || goto fail )
echo [P1-B] max_open=2 @ 1.5%% (=3%%)...
if not exist "%OUT%\P1_B_open2_r1p5\backtest_report.txt" ( "%PY%" "%SCRIPT%" %DYN% --max-open 2 --risk 1.5 --out-dir "%OUT%\P1_B_open2_r1p5" || goto fail )
echo [P1-C] max_open=2 @ 2%% (=4%%)...
if not exist "%OUT%\P1_C_open2_r2\backtest_report.txt" ( "%PY%" "%SCRIPT%" %DYN% --max-open 2 --risk 2 --out-dir "%OUT%\P1_C_open2_r2" || goto fail )

REM ===================== PHASE 2 — TP sweep =====================
REM fixed-lot 0.01 for fast, clean R comparison (TP affects R, not sizing)
set "TPB=%YEAR% --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1"

echo [P2 Ranging 1.6] ...
set QGAI_TP_REGIME_VALS=1.6,1.0,0.8
if not exist "%OUT%\P2_Rng1p6\backtest_report.txt" ( "%PY%" "%SCRIPT%" %TPB% --out-dir "%OUT%\P2_Rng1p6" || goto fail )
echo [P2 Ranging 2.4] ...
set QGAI_TP_REGIME_VALS=2.4,1.0,0.8
if not exist "%OUT%\P2_Rng2p4\backtest_report.txt" ( "%PY%" "%SCRIPT%" %TPB% --out-dir "%OUT%\P2_Rng2p4" || goto fail )
echo [P2 Ranging 2.8] ...
set QGAI_TP_REGIME_VALS=2.8,1.0,0.8
if not exist "%OUT%\P2_Rng2p8\backtest_report.txt" ( "%PY%" "%SCRIPT%" %TPB% --out-dir "%OUT%\P2_Rng2p8" || goto fail )

echo [P2 Trending 0.8] ...
set QGAI_TP_REGIME_VALS=2.0,0.8,0.8
if not exist "%OUT%\P2_Trn0p8\backtest_report.txt" ( "%PY%" "%SCRIPT%" %TPB% --out-dir "%OUT%\P2_Trn0p8" || goto fail )
echo [P2 Trending 1.2] ...
set QGAI_TP_REGIME_VALS=2.0,1.2,0.8
if not exist "%OUT%\P2_Trn1p2\backtest_report.txt" ( "%PY%" "%SCRIPT%" %TPB% --out-dir "%OUT%\P2_Trn1p2" || goto fail )
echo [P2 Trending 1.4] ...
set QGAI_TP_REGIME_VALS=2.0,1.4,0.8
if not exist "%OUT%\P2_Trn1p4\backtest_report.txt" ( "%PY%" "%SCRIPT%" %TPB% --out-dir "%OUT%\P2_Trn1p4" || goto fail )

echo [P2 Volatile 0.6] ...
set QGAI_TP_REGIME_VALS=2.0,1.0,0.6
if not exist "%OUT%\P2_Vol0p6\backtest_report.txt" ( "%PY%" "%SCRIPT%" %TPB% --out-dir "%OUT%\P2_Vol0p6" || goto fail )
echo [P2 Volatile 1.0] ...
set QGAI_TP_REGIME_VALS=2.0,1.0,1.0
if not exist "%OUT%\P2_Vol1p0\backtest_report.txt" ( "%PY%" "%SCRIPT%" %TPB% --out-dir "%OUT%\P2_Vol1p0" || goto fail )
echo [P2 Volatile 1.2] ...
set QGAI_TP_REGIME_VALS=2.0,1.0,1.2
if not exist "%OUT%\P2_Vol1p2\backtest_report.txt" ( "%PY%" "%SCRIPT%" %TPB% --out-dir "%OUT%\P2_Vol1p2" || goto fail )

set QGAI_TP_REGIME_VALS=
echo.
echo ============================================================
echo ALL DONE %DATE% %TIME%.  Root: %OUT%
echo PHASE 1 (R + real DD): P1_A / P1_B / P1_C
echo PHASE 2 (TP R-compare, fixed-lot): P2_Rng* / P2_Trn* / P2_Vol*
echo   baseline (Rng2/Trn1/Vol0.8) fixed-lot = fullbt_hmm_10k_lot001 +350.2R
echo   pick the TP per regime with highest Total R vs that baseline.
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED %DATE% %TIME% — resume-safe: re-run to continue. ***
pause
exit /b 1
