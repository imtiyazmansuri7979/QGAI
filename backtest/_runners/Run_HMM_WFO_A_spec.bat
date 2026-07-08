@echo off
title QGAI - WFO A: HMM spec variant (ADX + abs DI_diff + band_width_pct)
REM Child of Run_HMM_AB_WFO.bat (run that one first - it does regen + workdir freeze).
REM Live models are SAFE: QGAI_ROOT points at the frozen workdir copy.
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ROOT=C:\QGAI_wfo_spec"
set "QGAI_HMM_VARIANT=spec"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   WFO A (spec) : weekly retrain, OOS 2025-06-29 to 2026-06-29
echo   Results: C:\QGAI\backtest\results\wfo_hmm_spec\
echo   Resume-safe: if it stops, run this bat again.
echo ============================================================
"%PY%" run_wfo.py --start 2025-06-29 --end 2026-06-29 --buf 0.15 --tp-equity 0 --risk 3 --tp-regime --results-dir wfo_hmm_spec
echo.
echo DONE. Summary: C:\QGAI\backtest\results\wfo_hmm_spec\_WFO_SUMMARY.txt
echo Compare vs baseline wfo_live_match_015 = +483.1R  (profit-first)
pause
