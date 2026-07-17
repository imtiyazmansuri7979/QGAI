@echo off
setlocal
chcp 65001 >nul
title QGAI - EXIT03 - Peak-Ratchet Profit Lock TEST (2-week, 2 arms)

REM =====================================================================
REM  Registry ID: EXIT03  (exit work stream)
REM
REM  Peak-ratchet profit lock: once a trade's peak R reaches the trigger,
REM  raise virtual SL to lock a floor R — one-way, never lowers back.
REM
REM  TEST run: 2-week window, 2 arms (baseline + one setting) for error
REM  checking before the full 9-arm sweep.
REM
REM  Arms:
REM    000 = baseline (no peak-lock, current config)
REM    001 = trigger 1.0R, floor 0.4R
REM
REM  Estimated time: ~5 min (2 arms x ~2.5 min/arm)
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "ENGINE=%ROOT%\engine"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "FROM=2026-06-01"
set "TO=2026-06-15"
set "BASE_OUT=%ROOT%\backtest\results\exit_workstream\EXIT03_peak_ratchet_lock_TEST"

cd /d "%ENGINE%"

echo ============================================================
echo   EXIT03 - PEAK-RATCHET PROFIT LOCK  (TEST - 2 weeks)
echo   Period : %FROM% to %TO%
echo   Arms   : 2 (baseline + trigger=1.0/floor=0.4)
echo   Output : %BASE_OUT%
echo   %DATE% %TIME%
echo.
echo   Estimated time: ~5 min
echo ============================================================

REM --- ARM 000: Baseline (no peak-lock) --------------------------
set "TAG=EXIT03_TEST_000_baseline"
set "OUT=%BASE_OUT%\%TAG%"
echo.
echo --- ARM 000: BASELINE (no peak-lock) ---
"%PY%" backtest_replay.py --from %FROM% --to %TO% --fixed-lot 0.01 --ratchet on --no-resume --out-dir "%OUT%"
if %ERRORLEVEL% neq 0 echo *** ARM 000 FAILED *** & goto :done

REM --- ARM 001: trigger=1.0R, floor=0.4R -------------------------
set "TAG=EXIT03_TEST_001_t1.0_f0.4"
set "OUT=%BASE_OUT%\%TAG%"
echo.
echo --- ARM 001: PEAK-LOCK trigger=1.0R floor=0.4R ---
"%PY%" backtest_replay.py --from %FROM% --to %TO% --fixed-lot 0.01 --ratchet on --no-resume --out-dir "%OUT%" --peak-lock-trigger 1.0 --peak-lock-floor 0.4
if %ERRORLEVEL% neq 0 echo *** ARM 001 FAILED *** & goto :done

echo.
echo ============================================================
echo   EXIT03 TEST DONE
echo   Compare results in: %BASE_OUT%
echo ============================================================

:done
pause
exit /b %ERRORLEVEL%
