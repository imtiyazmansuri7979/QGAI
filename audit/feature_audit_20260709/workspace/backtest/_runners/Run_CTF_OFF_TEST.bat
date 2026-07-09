@echo off
setlocal
chcp 65001 >nul

REM =====================================================================
REM  CTF-OFF TEST — Fable-5 Rank 1: pure EA counter-trend-fade block A/B
REM  30-day smoke, gate FORCED OFF via env QGAI_CTF_FADE=0
REM  Verify: 0 blocked_by=ctf_fade rows in signals CSV.
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT=C:\QGAI\backtest\results\ctf_off_A_B\TEST_30d_ctfOFF"

set QGAI_CTF_FADE=0

echo ============================================================
echo TEST: CTF-fade OFF  30-day smoke
echo   QGAI_CTF_FADE=%QGAI_CTF_FADE%  (must be 0)
echo ============================================================
cd /d "%ROOT%\engine"
%PY% "%SCRIPT%" --from 2026-05-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "%OUT%"
if errorlevel 1 goto fail

echo.
echo TEST DONE. Check %OUT%\backtest_signals_st-htf.csv:
echo   blocked_by "ctf_fade" count should be 0 (gate forced OFF).
echo If OK -^> run Run_CTF_OFF_FULL.bat
pause
exit /b 0

:fail
echo *** TEST FAILED — do NOT run FULL bat yet. ***
pause
exit /b 1
