@echo off
title QGAI - Full Backtest Report (replay, real model)
REM Runs backtest_replay.py over the FULL period with the real ML model and the
REM LIVE exit config (ratchet H1, buf 0.20, far TP, line trail). Produces the
REM full report: WR/PF/Avg R + BY REGIME + BY HOUR + BY MONTH + exit reasons.
REM Fast (one pass, real model). NOTE: single model over whole period = mild
REM look-ahead on early months (absolute optimistic); regime/hour breakdowns are
REM still very useful for INSIGHT. For honest absolute -> use OOS window or WFO.
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QGAI_ABLATE="
set "OUT=C:\QGAI\backtest\results\report"
if not exist "%OUT%" mkdir "%OUT%"
cd /d "C:\QGAI\engine"
echo ============================================================
echo   FULL BACKTEST REPORT (replay, real model, live config)
echo   Period: 2025-09-01 -^> 2026-06-12
echo   Output: %OUT%\backtest_report.txt  (+ trade log)
echo ============================================================
echo.
"%PY%" backtest_replay.py --from 2025-09-01 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.30 --ratchet on --ratchet-buf-pct 0.20 --tp-equity-pct 0 --skip-counter-trend --fixed-lot 0.01 --out-dir "%OUT%"
echo.
echo ============================================================
echo   Done. Open:  %OUT%\backtest_report.txt
echo   (BY REGIME / BY HOUR / BY MONTH breakdowns included)
echo ============================================================
pause
