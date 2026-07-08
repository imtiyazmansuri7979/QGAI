@echo off
title QGAI - WFO B: HMM rel variant (ADX + di_eff + band_rel) [RECOMMENDED]
REM Child of Run_HMM_AB_WFO.bat (run that one - it does regen + workdir freeze).
REM Live models are SAFE: QGAI_ROOT points at the frozen workdir copy.
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ROOT=C:\QGAI_wfo_rel"
set "QGAI_HMM_VARIANT=rel"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   WFO B (rel) : weekly retrain, OOS 2025-06-29 - 2026-06-29
echo   Results: C:\QGAI\backtest\results\wfo_hmm_rel\
echo   Resume-safe: if it stops, run this bat again.
echo ============================================================
"%PY%" run_wfo.py --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --results-dir wfo_hmm_rel
echo.
echo DONE. Summary: C:\QGAI\backtest\results\wfo_hmm_rel\_WFO_SUMMARY.txt
echo Compare vs baseline wfo_live_match_015 = +483.1R  (profit-first)
pause
