@echo off
title QGAI - FULL BACKTEST : RANGE FILTER OFF (A/B) : 1 year, $10k, 0.01 lot, corrected rel HMM
REM ---------------------------------------------------------------------------
REM A/B TEST — does the H4 range-phase filter block PROFITABLE trades?
REM Same config as Run_FullBT_HMM_10k_lot001.bat but with --no-range-skip (allow
REM range/chop trades). Compare total R / regime breakdown vs the range-ON run:
REM   range ON  -> backtest\results\fullbt_hmm_10k_lot001\
REM   range OFF -> backtest\results\fullbt_norange_10k_lot001\   (this run)
REM If range-OFF total R is HIGHER, the filter is costing profit (relax/remove).
REM If LOWER, the filter is correct (range trades are net-negative, as config claims).
REM Run Run_FullBT_HMM_10k_lot001.bat (range ON) FIRST for the comparison.
REM ---------------------------------------------------------------------------
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_HMM_VARIANT=rel"
cd /d "C:\QGAI\engine"
"%PY%" backtest_replay.py --from 2025-06-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --no-range-skip --out-dir "C:\QGAI\backtest\results\fullbt_norange_10k_lot001"
echo.
echo DONE (range OFF). Compare backtest_report.txt total R vs fullbt_hmm_10k_lot001 (range ON).
echo   Higher R here = filter was blocking profit.  Lower = filter is correct.
pause
