@echo off
title QGAI - Buffer Sweep (regime-wise, latest settings)
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "C:\QGAI\engine"
set "RPT=C:\QGAI\backtest\results\replay_logs\backtest_report.txt"
set "OUT=C:\QGAI\backtest\results\bufsweep"
if not exist "%OUT%" mkdir "%OUT%"
echo ============================================================
echo   QGAI - RATCHET BUFFER SWEEP   0.10 / 0.15 / 0.20 / 0.25 / 0.30 %%
echo ------------------------------------------------------------
echo   LATEST settings (auto via config): 42-feat model + forming
echo   H1 line (ratchet_htf_forming=True) + regime-TP.
echo   fixed-lot 0.01 = clean comparable R (Stage-1 exit ranking).
echo   Range: 2025-06-29 -^> 2026-06-29 (1 year).  Per-buf -^> bufsweep\
echo ============================================================

for %%B in (0.10 0.15 0.20 0.25 0.30) do (
    echo.
    echo ===================  BUFFER %%B%%  ===================
    "%PY%" backtest_replay.py --from 2025-06-29 --to 2026-06-29 --ratchet-buf-pct %%B --tp-regime --fixed-lot 0.01
    if exist "%RPT%" ( copy /Y "%RPT%" "%OUT%\buf_%%B.txt" >nul && echo   [saved] bufsweep\buf_%%B.txt )
)

echo.
echo ============================================================
echo   DONE. Reports: %OUT%\buf_*.txt
echo   Compare the "BY REGIME" block in each to pick the best
echo   buffer per Ranging / Trending / Volatile.
echo ============================================================
pause
