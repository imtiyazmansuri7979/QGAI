@echo off
setlocal
chcp 65001 >nul
title QGAI - SMMA + ADX-DI Rule-Based Score Sweep (standalone research, no AI)

REM =====================================================================
REM  Standalone rule-based research bot (Imtiyaz, EA16 Research).
REM  Finds the RAW edge of the 2-SMMA (20SMA_TrendSignals_Hybrid.mq5) and
REM  ADX-DI logic with NO AI model, NO win_prob, NO 67-feature logic, NO
REM  HMM entry gate, NO probability threshold, NO news/slot/hard-ADX filter.
REM  Two independent scores only, swept over all 15 timeframe-sets
REM  (M15/M30/H1/H4) x 3 ADX versions to find which timeframe combination
REM  carries the edge. Winner logic later seeds compact AI features.
REM
REM  FULLY ISOLATED: loads only OHLC, loads/writes NO model file, never
REM  imports inference/bridge/train. Output goes to
REM  backtest\results\smma_adx_score_sweep\ . Safe to run while the live
REM  bot trades. Existing production code is never touched.
REM
REM  Phase-1 (3-month screen) full 735-config sweep ~= 20 seconds.
REM  Resume-safe: re-running skips already-completed configs.
REM
REM  Usage:
REM    RUN_SMMA_ADX_SCORE_SWEEP.bat                 (uses config json dates)
REM    RUN_SMMA_ADX_SCORE_SWEEP.bat 2025-06-23 2026-06-29   (1-year holdout)
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

set "DATEARG="
if not "%~1"=="" if not "%~2"=="" set "DATEARG=--start %~1 --end %~2"

echo ============================================================
echo   SMMA + ADX-DI SCORE SWEEP
echo   %DATE% %TIME%
echo   Date override: %DATEARG%
echo ============================================================

echo.
echo [1/2] Benchmark (time one config, estimate full sweep)...
"%PY%" research_smma_adx_score_sweep.py --benchmark %DATEARG%

echo.
echo [2/2] Full sweep...
"%PY%" research_smma_adx_score_sweep.py %DATEARG%
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   DONE. Results in: backtest\results\smma_adx_score_sweep\
echo     score_sweep_report.txt         (top candidates + Pareto leaders)
echo     score_sweep_summary.csv        (every config, raw metrics + rank)
echo     score_sweep_top_candidates.csv (top 20 OK configs)
echo     score_sweep_trade_detail.csv   (per-trade rows)
echo     score_sweep_monthly.csv        (per-config monthly R)
echo   Resume-safe: re-run to continue an interrupted sweep.
echo ============================================================
pause
exit /b %RC%
