@echo off
title QGAI - FULL BACKTEST TEST : 1 week, $10k, 0.01 lot, corrected rel HMM (signals+trades CSV)
REM ---------------------------------------------------------------------------
REM TEST-RUN FIRST (house rule): 1-week quick check before the full year.
REM Current corrected rel HMM (data\models\final) + leak-free adx_merged.
REM Live-faithful: ratchet htf + regime-TP + buffer 0.15, fixed 0.01 lot, $10k.
REM Output folder gets: backtest_report.txt + backtest_signals_*.csv (every bar)
REM + backtest_trades_*.csv (each trade) + backtest_summary_*.csv.
REM If clean -> Run_FullBT_HMM_10k_lot001.bat
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_HMM_VARIANT=rel"
cd /d "C:\QGAI\engine"
"%PY%" backtest_replay.py --from 2025-06-29 --to 2025-07-06 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --out-dir "C:\QGAI\backtest\results\fullbt_hmm_10k_lot001_TEST"
echo.
echo TEST DONE. Check folder backtest\results\fullbt_hmm_10k_lot001_TEST\ has:
echo   backtest_report.txt, backtest_signals_*.csv, backtest_trades_*.csv, backtest_summary_*.csv
echo Then run Run_FullBT_HMM_10k_lot001.bat
pause
