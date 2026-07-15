@echo off
setlocal
chcp 65001 >nul
title QGAI - SMMA + ADX-DI Live Snapshot Logger (forming candles, raw data capture)

REM =====================================================================
REM  Complete live (forming) snapshot logger (Imtiyaz, EA16 Research).
REM  At EVERY M15 decision bar, captures the full evolving state of BOTH
REM  the 2-SMMA (20SMA_TrendSignals_Hybrid.mq5) and ADX-DI across
REM  M15/M30/H1/H4, using PARTIAL-candle reconstruction for M30/H1/H4
REM  (16 distinct H4 snapshots per H4 period). ~180 fields per timeframe +
REM  ~34 aggregate fields. No future HTF candle data; no backward-fill.
REM
REM  RAW DATA CAPTURE ONLY -- does NOT make trade decisions. Entry logic
REM  stays in research_smma_adx_score_sweep.py and uses only baseline
REM  direction scores. Every slope/distance/persistence/band/transition
REM  field here is used_for_entry=0 (analysis / future AI features), tagged
REM  in smma_adx_data_dictionary.csv.
REM
REM  FULLY ISOLATED: loads only OHLC, no model/win_prob/HMM/threshold/news/
REM  slot filter, never imports inference/bridge/train. Safe while the live
REM  bot trades. Output: backtest\results\smma_adx_snapshot\ .
REM
REM  Usage:
REM    RUN_SMMA_ADX_SNAPSHOT_LOGGER.bat                 (config default dates)
REM    RUN_SMMA_ADX_SNAPSHOT_LOGGER.bat 2025-06-23 2026-06-29   (1-year)
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\engine"

set "DATEARG="
if not "%~1"=="" if not "%~2"=="" set "DATEARG=--start %~1 --end %~2"

echo ============================================================
echo   SMMA + ADX-DI LIVE SNAPSHOT LOGGER
echo   %DATE% %TIME%
echo   Date override: %DATEARG%
echo ============================================================

"%PY%" research_smma_adx_snapshot_logger.py %DATEARG%
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo   DONE. Results in: backtest\results\smma_adx_snapshot\
echo     smma_adx_snapshot_all.csv        (long: one row per decision x TF)
echo     smma_adx_snapshot_M15/M30/H1/H4.csv
echo     smma_adx_aggregate_scores.csv    (4-TF aggregate per decision)
echo     smma_adx_transition_events.csv   (DI/price crosses only)
echo     smma_adx_leakage_audit.csv       (no-lookahead brute-force recheck)
echo     smma_adx_data_dictionary.csv     (per-column source/causal/entry-use)
echo     smma_adx_snapshot_report.txt
echo ============================================================
pause
exit /b %RC%
