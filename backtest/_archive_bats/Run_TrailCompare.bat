@echo off
REM ============================================================
REM  TRAIL-MODE COMPARISON  (SEQUENTIAL — one at a time)
REM ------------------------------------------------------------
REM  Runs the 6 stop-trail modes one by one in THIS window.
REM  Light on memory (only one backtest loads at a time).
REM  Each writes its own CSV + trail_<mode>.txt (no clobber).
REM  Trail mode only changes the EXIT (same entries/model) — fair.
REM  Resume-friendly: if you stop, already-finished trail_*.txt
REM  stay; just run again (it re-does all 6, ~few min each).
REM ============================================================
setlocal
set PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set OUT=C:\QGAI\backtest\results\trail_compare
if not exist "%OUT%" mkdir "%OUT%"
cd /d C:\QGAI\engine

set COMMON=--from 2025-09-01 --to 2026-06-12 --equity 10000 --risk 3 --spread 0.20 --ratchet on --ratchet-buf-pct 0.20 --tp-equity-pct 3 --skip-counter-trend --fixed-lot 0.01

for %%M in (line off after1r be htf regime) do (
    echo.
    echo ============================================================
    echo  Running stop-trail = %%M   ^(one at a time^)
    echo ============================================================
    "%PY%" backtest_replay.py %COMMON% --stop-trail %%M --out-dir "%OUT%" > "%OUT%\trail_%%M.txt" 2>&1
    echo   done -^> trail_%%M.txt
)

echo.
echo ============================================================
echo  ALL 6 TRAIL MODES DONE (sequential).
echo  Results: %OUT%\trail_*.txt
echo  Tell Claude "done".
echo ============================================================
pause
