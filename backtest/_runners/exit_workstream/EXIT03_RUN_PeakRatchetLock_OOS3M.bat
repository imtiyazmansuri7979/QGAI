@echo off
setlocal
chcp 65001 >nul
title QGAI - EXIT03 - Peak-Ratchet Profit Lock FULL (3-month OOS, 9 arms)

REM =====================================================================
REM  Registry ID: EXIT03  (exit work stream)
REM
REM  Peak-ratchet profit lock: once a trade's peak R reaches the trigger,
REM  raise virtual SL to lock a floor R — one-way, never lowers back.
REM
REM  FULL 9-arm A/B sweep (3x3 grid):
REM    trigger = {0.8, 1.0, 1.2}  x  floor = {0.2, 0.4, 0.6}
REM
REM  Period: 3-month OOS (2026-03-29 to 2026-06-29)
REM
REM  Arms:
REM    000 = baseline (no peak-lock)
REM    001 = t0.8 f0.2    004 = t1.0 f0.2    007 = t1.2 f0.2
REM    002 = t0.8 f0.4    005 = t1.0 f0.4    008 = t1.2 f0.4
REM    003 = t0.8 f0.6    006 = t1.0 f0.6    009 = t1.2 f0.6
REM
REM  Estimated time: ~200 min (10 arms x ~20 min/arm for 3-month)
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "ENGINE=%ROOT%\engine"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "FROM=2026-03-29"
set "TO=2026-06-29"
set "BASE_OUT=%ROOT%\backtest\results\exit_workstream\EXIT03_peak_ratchet_lock_OOS3M"

cd /d "%ENGINE%"

echo ============================================================
echo   EXIT03 - PEAK-RATCHET PROFIT LOCK  (3-month OOS, 9+1 arms)
echo   Period : %FROM% to %TO%
echo   Arms   : 10 (baseline + 3x3 trigger x floor grid)
echo   Output : %BASE_OUT%
echo   %DATE% %TIME%
echo.
echo   Estimated time: ~200 min (~3.3 hours)
echo ============================================================

set "COMMON=--from %FROM% --to %TO% --fixed-lot 0.01 --ratchet on --no-resume"

REM --- ARM 000: Baseline (no peak-lock) --------------------------
set "TAG=EXIT03_OOS3M_000_baseline"
echo.
echo --- [1/10] ARM 000: BASELINE (no peak-lock) ---
echo     %TIME%
"%PY%" backtest_replay.py %COMMON% --out-dir "%BASE_OUT%\%TAG%"
if %ERRORLEVEL% neq 0 echo *** ARM 000 FAILED *** & goto :done

REM --- trigger=0.8 -----------------------------------------------
set "TAG=EXIT03_OOS3M_001_t0.8_f0.2"
echo.
echo --- [2/10] ARM 001: trigger=0.8 floor=0.2 ---
echo     %TIME%
"%PY%" backtest_replay.py %COMMON% --out-dir "%BASE_OUT%\%TAG%" --peak-lock-trigger 0.8 --peak-lock-floor 0.2
if %ERRORLEVEL% neq 0 echo *** ARM 001 FAILED *** & goto :done

set "TAG=EXIT03_OOS3M_002_t0.8_f0.4"
echo.
echo --- [3/10] ARM 002: trigger=0.8 floor=0.4 ---
echo     %TIME%
"%PY%" backtest_replay.py %COMMON% --out-dir "%BASE_OUT%\%TAG%" --peak-lock-trigger 0.8 --peak-lock-floor 0.4
if %ERRORLEVEL% neq 0 echo *** ARM 002 FAILED *** & goto :done

set "TAG=EXIT03_OOS3M_003_t0.8_f0.6"
echo.
echo --- [4/10] ARM 003: trigger=0.8 floor=0.6 ---
echo     %TIME%
"%PY%" backtest_replay.py %COMMON% --out-dir "%BASE_OUT%\%TAG%" --peak-lock-trigger 0.8 --peak-lock-floor 0.6
if %ERRORLEVEL% neq 0 echo *** ARM 003 FAILED *** & goto :done

REM --- trigger=1.0 -----------------------------------------------
set "TAG=EXIT03_OOS3M_004_t1.0_f0.2"
echo.
echo --- [5/10] ARM 004: trigger=1.0 floor=0.2 ---
echo     %TIME%
"%PY%" backtest_replay.py %COMMON% --out-dir "%BASE_OUT%\%TAG%" --peak-lock-trigger 1.0 --peak-lock-floor 0.2
if %ERRORLEVEL% neq 0 echo *** ARM 004 FAILED *** & goto :done

set "TAG=EXIT03_OOS3M_005_t1.0_f0.4"
echo.
echo --- [6/10] ARM 005: trigger=1.0 floor=0.4 ---
echo     %TIME%
"%PY%" backtest_replay.py %COMMON% --out-dir "%BASE_OUT%\%TAG%" --peak-lock-trigger 1.0 --peak-lock-floor 0.4
if %ERRORLEVEL% neq 0 echo *** ARM 005 FAILED *** & goto :done

set "TAG=EXIT03_OOS3M_006_t1.0_f0.6"
echo.
echo --- [7/10] ARM 006: trigger=1.0 floor=0.6 ---
echo     %TIME%
"%PY%" backtest_replay.py %COMMON% --out-dir "%BASE_OUT%\%TAG%" --peak-lock-trigger 1.0 --peak-lock-floor 0.6
if %ERRORLEVEL% neq 0 echo *** ARM 006 FAILED *** & goto :done

REM --- trigger=1.2 -----------------------------------------------
set "TAG=EXIT03_OOS3M_007_t1.2_f0.2"
echo.
echo --- [8/10] ARM 007: trigger=1.2 floor=0.2 ---
echo     %TIME%
"%PY%" backtest_replay.py %COMMON% --out-dir "%BASE_OUT%\%TAG%" --peak-lock-trigger 1.2 --peak-lock-floor 0.2
if %ERRORLEVEL% neq 0 echo *** ARM 007 FAILED *** & goto :done

set "TAG=EXIT03_OOS3M_008_t1.2_f0.4"
echo.
echo --- [9/10] ARM 008: trigger=1.2 floor=0.4 ---
echo     %TIME%
"%PY%" backtest_replay.py %COMMON% --out-dir "%BASE_OUT%\%TAG%" --peak-lock-trigger 1.2 --peak-lock-floor 0.4
if %ERRORLEVEL% neq 0 echo *** ARM 008 FAILED *** & goto :done

set "TAG=EXIT03_OOS3M_009_t1.2_f0.6"
echo.
echo --- [10/10] ARM 009: trigger=1.2 floor=0.6 ---
echo     %TIME%
"%PY%" backtest_replay.py %COMMON% --out-dir "%BASE_OUT%\%TAG%" --peak-lock-trigger 1.2 --peak-lock-floor 0.6
if %ERRORLEVEL% neq 0 echo *** ARM 009 FAILED *** & goto :done

echo.
echo ============================================================
echo   EXIT03 FULL SWEEP DONE  (%TIME%)
echo   Results: %BASE_OUT%
echo   Compare all 10 *_report.txt files for Total R / WR / PF
echo ============================================================

:done
pause
exit /b %ERRORLEVEL%
