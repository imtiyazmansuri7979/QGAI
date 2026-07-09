@echo off
setlocal
chcp 65001 >nul

REM =====================================================================
REM  CTF-OFF FULL — Fable-5 Rank 1: full-year live-parity A/B
REM  Compare vs baseline `fullbt_hmm_10k_lot001` (+350.2R).
REM  Expected: +5 to +25R lift if CTF was cutting the 0/3-aligned edge.
REM  Worst case: ~−15R, one-line revert (set QGAI_CTF_FADE=1 or config).
REM =====================================================================

set "ROOT=C:\QGAI"
set "PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT=C:\QGAI\engine\backtest_replay.py"
set "OUT=C:\QGAI\backtest\results\ctf_off_A_B\FULL_1yr_ctfOFF"

set QGAI_CTF_FADE=0

echo ============================================================
echo FULL: CTF-fade OFF  1-year live-parity  %DATE% %TIME%
echo   QGAI_CTF_FADE=%QGAI_CTF_FADE%  (must be 0)
echo   SCRIPT = %SCRIPT%
echo   OUT    = %OUT%
echo ============================================================
if not "%QGAI_CTF_FADE%"=="0" (
  echo *** ABORT: QGAI_CTF_FADE is not 0 - gate would still be ON. ***
  pause
  exit /b 1
)

cd /d "%ROOT%\engine"
%PY% "%SCRIPT%" --from 2025-06-29 --to 2026-06-29 --equity 10000 --fixed-lot 0.01 --risk 3 --ratchet auto --ratchet-buf-pct 0.15 --tp-regime --tp-equity-pct 0 --max-open 1 --out-dir "%OUT%"
if errorlevel 1 goto fail

echo.
echo ============================================================
echo DONE %DATE% %TIME%
echo Compare:
echo   Baseline (CTF ON) : C:\QGAI\backtest\results\fullbt_hmm_10k_lot001   +350.2R
echo   CTF OFF          : %OUT%
echo Look at: Total R, PF, DD, trades unblocked (were they winners?).
echo ============================================================
pause
exit /b 0

:fail
echo *** FAILED — check log. ***
pause
exit /b 1
