@echo off
title QGAI - FULL BACKTEST : 1 year, $10k, 0.01 lot, corrected rel HMM (signals+trades CSV)
REM ---------------------------------------------------------------------------
REM Full 1-year backtest on the CURRENT corrected rel HMM (data\models\final)
REM + leak-free adx_merged. Live-faithful config: ratchet htf + regime-TP +
REM buffer 0.15, fixed 0.01 lot, $10k equity, risk 3%.
REM Run Run_FullBT_HMM_10k_lot001_TEST.bat FIRST (1 week) — only run this if clean.
REM
REM NOTE: single-model IN-SAMPLE backtest (one model over the whole year). The
REM leak-free OUT-OF-SAMPLE honest baseline is the WFO = wfo_asof_rel (+393.7R).
REM
REM Output folder (one place, everything for this run):
REM   backtest\results\fullbt_hmm_10k_lot001\
REM     backtest_report.txt          (summary: Trades/WR/PF/Max DD/regime)
REM     backtest_signals_*.csv       (EVERY M15 bar: signal, probs, ADX, ts_*, blocked_by)
REM     backtest_trades_*.csv        (EACH trade: entry/exit/R/pnl + f_* features)
REM     backtest_summary_*.csv       (one-row run summary)
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_HMM_VARIANT=rel"
cd /d "C:\QGAI\engine"
"%PY%" backtest_replay.py --from 2025-06-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --out-dir "C:\QGAI\backtest\results\fullbt_hmm_10k_lot001"
echo.
echo FULL DONE. Open backtest\results\fullbt_hmm_10k_lot001\ :
echo   backtest_report.txt  +  backtest_signals_*.csv  +  backtest_trades_*.csv  +  backtest_summary_*.csv
pause
