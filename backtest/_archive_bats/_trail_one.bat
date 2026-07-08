@echo off
REM Runs ONE stop-trail mode (arg %1). Called by Run_TrailCompare.bat.
setlocal
set PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set OUT=C:\QGAI\backtest\results\trail_compare
if not exist "%OUT%" mkdir "%OUT%"
cd /d C:\QGAI\engine
"%PY%" backtest_replay.py --from 2025-09-01 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.20 --tp-equity-pct 3 --skip-counter-trend --fixed-lot 0.01 --stop-trail %1 --out-dir "%OUT%" > "%OUT%\trail_%1.txt" 2>&1
echo done %1
